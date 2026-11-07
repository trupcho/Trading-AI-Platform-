//+------------------------------------------------------------------+
//| Trading AI DEMO Scalper v0.1                                      |
//| STARTER/EXPERIMENTAL: MQL5 COMPILATION NOT YET VERIFIED           |
//| Never places trades on live accounts. Orders OFF by default.     |
//| Chart timeframe: M1; broker symbol attached to chart.            |
//+------------------------------------------------------------------+
#property copyright "Trading AI Demo starter - research and learning only"
#property version "0.10"
#property strict
#include <Trade/Trade.mqh>

// Policies are market regimes, not individual order instructions.
enum ENUM_TAI_POLICY
  {
   TAI_HALT=0,
   TAI_BUY_ONLY=1,
   TAI_SELL_ONLY=2,
   TAI_BOTH=3
  };

input bool             InpEnableDemoOrders = false; // OFF by default
input ENUM_TAI_POLICY  InpTesterPolicy = TAI_HALT;  // Only in Strategy Tester
input double           InpRiskPct = 0.25;           // % of current equity per position
input double           InpDailyLossPct = 1.0;      // equity drawdown vs daily start
input double           InpMaxMarginPct = 35.0;     // % equity allocated to one position
input double           InpMaxSpreadPoints = 0.0;   // MUST configure per broker; 0 means reject
input double           InpAtrSLMultiplier = 1.5;
input double           InpAtrTPMultiplier = 2.0;
input double           InpRiskCostBuffer = 1.2;    // extra loss allowance, NOT slippage guarantee
input int              InpDeviationPoints = 20;
input int              InpMagic = 260711;
input int              InpPollSeconds = 15;
input string           InpGatewayBase = "http://127.0.0.1:8765";
input string           InpGatewayKey = "";

CTrade trade;
int g_fast = INVALID_HANDLE;
int g_slow = INVALID_HANDLE;
int g_atr = INVALID_HANDLE;
ENUM_TAI_POLICY g_policy = TAI_HALT;
long g_expires = 0;
datetime g_lastBar = 0;
string g_dailyKey = "";

bool IsTester()
  {
   return (MQLInfoInteger(MQL_TESTER) != 0);
  }

bool IsDemoEnvironment()
  {
   if(IsTester()) return true; // Strategy Tester never submits live orders
   return AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO;
  }

bool EnforceEnvironment()
  {
   if(!IsDemoEnvironment())
     {
      Print("TRADING AI: NON-DEMO ACCOUNT DETECTED. ALL ORDERS BLOCKED.");
      return false;
     }
   if(AccountInfoString(ACCOUNT_CURRENCY) != "EUR")
     {
      Print("TRADING AI: account currency must be EUR for this demo preset.");
      return false;
     }
   return true;
  }

bool InternetReady()
  {
   return StringFind(InpGatewayBase, "http://127.0.0.1:") == 0 &&
          StringLen(InpGatewayKey) >= 24;
  }

void UpdateDailyBaseline()
  {
   // Persisted terminal-global value survives EA restart during the same broker day.
   string key = "TAID_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_" + TimeToString(TimeCurrent(), TIME_DATE);
   if(key != g_dailyKey)
     {
      g_dailyKey = key;
      if(!GlobalVariableCheck(g_dailyKey))
         GlobalVariableSet(g_dailyKey, AccountInfoDouble(ACCOUNT_EQUITY));
     }
  }

bool DailyLossHit()
  {
   UpdateDailyBaseline();
   if(!GlobalVariableCheck(g_dailyKey)) return true;
   double baseline = GlobalVariableGet(g_dailyKey);
   if(baseline <= 0 || InpDailyLossPct <= 0 || InpDailyLossPct > 10) return true;
   return AccountInfoDouble(ACCOUNT_EQUITY) <= baseline * (1.0 - InpDailyLossPct / 100.0);
  }

void CloseOurPositionsAfterDailyStop()
  {
   // This is a best-effort emergency response, not a guaranteed stop at a price.
   for(int i=PositionsTotal()-1; i>=0; --i)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(!trade.PositionClose(ticket))
         Print("TRADING AI: emergency close failed ticket=", ticket, " retcode=",trade.ResultRetcode());
     }
  }

bool ParsePolicy(const string wire)
  {
   string parts[];
   if(StringSplit(wire, '|', parts) != 5) return false;
   if(parts[0] != "V1" || parts[1] != _Symbol) return false;
   long issued = (long)StringToInteger(parts[3]);
   long expiry = (long)StringToInteger(parts[4]);
   long now = (long)TimeGMT();
   if(issued <= 0 || expiry <= issued || expiry-issued > 900 || issued > now+60 || expiry <= now) return false;
   if(parts[2] == "HALT") g_policy = TAI_HALT;
   else if(parts[2] == "BUY_ONLY") g_policy = TAI_BUY_ONLY;
   else if(parts[2] == "SELL_ONLY") g_policy = TAI_SELL_ONLY;
   else if(parts[2] == "BOTH") g_policy = TAI_BOTH;
   else return false;
   g_expires = expiry;
   return true;
  }

void RefreshGatewayPolicy()
  {
   // Fail closed on malformed, absent, unauthorized or stale gateway response.
   g_policy = TAI_HALT;
   g_expires = 0;
   if(!InternetReady()) return;
   char empty[];
   char response[];
   string responseHeaders;
   string headers = "X-API-Key: " + InpGatewayKey + "\r\n";
   string url = InpGatewayBase + "/v1/mt5/policy?symbol=" + _Symbol;
   int code = WebRequest("GET", url, headers, 2500, empty, response, responseHeaders);
   if(code != 200)
     {
      Print("TRADING AI: gateway policy request denied/unavailable, HTTP=",code);
      return;
     }
   string body = CharArrayToString(response, 0, -1, CP_UTF8);
   if(!ParsePolicy(body))
      Print("TRADING AI: gateway policy malformed or expired; HALT");
  }

void SendHeartbeat()
  {
   if(!InternetReady() || !IsDemoEnvironment()) return;
   string body = StringFormat("{\"symbol\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"positions\":%d,\"demo\":true}",
       _Symbol, AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY), PositionsTotal());
   char data[];
   int n = StringToCharArray(body, data, 0, -1, CP_UTF8);
   if(n <= 1) return;
   ArrayResize(data,n-1); // Exclude terminating NUL from JSON request.
   char response[];
   string responseHeaders;
   string headers = "X-API-Key: " + InpGatewayKey + "\r\nContent-Type: application/json\r\n";
   WebRequest("POST", InpGatewayBase+"/v1/mt5/heartbeat", headers, 2500, data, response, responseHeaders);
  }

int OnInit()
  {
   if(_Period != PERIOD_M1)
     {
      Print("Trading AI: attach to a M1 chart only");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(!EnforceEnvironment())
      return INIT_PARAMETERS_INCORRECT;
   if(InpRiskPct <= 0 || InpRiskPct > 0.25 || InpDailyLossPct <= 0 || InpDailyLossPct > 1.0 ||
      InpMaxMarginPct <= 0 || InpMaxMarginPct > 35 || InpAtrSLMultiplier < 1.0 ||
      InpAtrTPMultiplier <= 0 || InpRiskCostBuffer < 1.0 || InpPollSeconds < 5)
      return INIT_PARAMETERS_INCORRECT;
   g_fast = iMA(_Symbol, PERIOD_M1, 9, 0, MODE_EMA, PRICE_CLOSE);
   g_slow = iMA(_Symbol, PERIOD_M1, 21, 0, MODE_EMA, PRICE_CLOSE);
   g_atr = iATR(_Symbol, PERIOD_M1, 14);
   if(g_fast==INVALID_HANDLE || g_slow==INVALID_HANDLE || g_atr==INVALID_HANDLE)
      return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   UpdateDailyBaseline();
   if(IsTester())
     {
      g_policy = InpTesterPolicy;  // Offline input; WebRequest unavailable in Strategy Tester.
     }
   else
      EventSetTimer(InpPollSeconds);
   Print("Trading AI v0.1 started DEMO ONLY. Orders enabled=",InpEnableDemoOrders);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_fast!=INVALID_HANDLE) IndicatorRelease(g_fast);
   if(g_slow!=INVALID_HANDLE) IndicatorRelease(g_slow);
   if(g_atr!=INVALID_HANDLE) IndicatorRelease(g_atr);
  }

void OnTimer()
  {
   if(!IsDemoEnvironment())
     {
      g_policy = TAI_HALT;
      return;
     }
   RefreshGatewayPolicy();
   SendHeartbeat();
  }

bool TradingAuthorized()
  {
   if(!InpEnableDemoOrders || !EnforceEnvironment()) return false;
   if(DailyLossHit())
     {
      CloseOurPositionsAfterDailyStop();
      return false;
     }
   if(PositionsTotal() > 0) return false;  // account-wide one-position cap
   if(!IsTester() && ((long)TimeGMT() >= g_expires || g_policy==TAI_HALT)) return false;
   if(IsTester() && g_policy==TAI_HALT) return false;
   if(InpMaxSpreadPoints <= 0) return false; // requires observed broker-specific value
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return false;
   return true;
  }

bool ComputeVolume(const ENUM_ORDER_TYPE orderType, const double open, const double sl, double &volume)
  {
   double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(minimum<=0 || maximum<minimum || step<=0) return false;
   double expectedPnL=0;
   double requiredMargin=0;
   if(!OrderCalcProfit(orderType,_Symbol,minimum,open,sl,expectedPnL) || expectedPnL>=0) return false;
   if(!OrderCalcMargin(orderType,_Symbol,minimum,open,requiredMargin) || requiredMargin<=0) return false;
   double riskBudget=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPct/100.0;
   double marginBudget=MathMin(AccountInfoDouble(ACCOUNT_EQUITY)*InpMaxMarginPct/100.0,
                               AccountInfoDouble(ACCOUNT_MARGIN_FREE)*0.80);
   double maxRiskLots=(riskBudget/(MathAbs(expectedPnL)*InpRiskCostBuffer))*minimum;
   double maxMarginLots=(marginBudget/requiredMargin)*minimum;
   double raw=MathMin(maximum, MathMin(maxRiskLots,maxMarginLots));
   volume=NormalizeDouble(MathFloor((raw+1e-10)/step)*step,8);
   if(volume+1e-10<minimum)
     {
      Print("Trading AI: SKIP — minimum lot exceeds € risk or margin budget. min=",minimum,
            " riskBudget=",DoubleToString(riskBudget,2)," ",AccountInfoString(ACCOUNT_CURRENCY));
      return false;
     }
   return true;
  }

void TryEntry(const ENUM_ORDER_TYPE type,const double atr)
  {
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.ask<=0 || tick.bid<=0) return;
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   if(point<=0) return;
   double spreadPts=(tick.ask-tick.bid)/point;
   if(spreadPts>InpMaxSpreadPoints)
     {
      Print("Trading AI: SKIP wide spread points=",DoubleToString(spreadPts,1));
      return;
     }
   if(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL) return;
   double open=(type==ORDER_TYPE_BUY)?tick.ask:tick.bid;
   double minStop=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
   double stopDistance=MathMax(atr*InpAtrSLMultiplier,minStop+2*point);
   double targetDistance=MathMax(atr*InpAtrTPMultiplier,minStop+2*point);
   if(stopDistance<=0 || targetDistance<=0) return;
   double sl=NormalizeDouble(open + ((type==ORDER_TYPE_BUY)?-stopDistance:stopDistance),digits);
   double tp=NormalizeDouble(open + ((type==ORDER_TYPE_BUY)?targetDistance:-targetDistance),digits);
   double volume=0;
   if(!ComputeVolume(type,open,sl,volume)) return;
   bool ok=false;
   if(type==ORDER_TYPE_BUY)
      ok=trade.Buy(volume,_Symbol,0.0,sl,tp,"TAI demo scalper");
   else
      ok=trade.Sell(volume,_Symbol,0.0,sl,tp,"TAI demo scalper");
   if(!ok || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_PLACED))
      Print("Trading AI: order rejected retcode=",trade.ResultRetcode()," ",trade.ResultRetcodeDescription());
  }

void OnTick()
  {
   if(!IsDemoEnvironment()) return;
   if(InpEnableDemoOrders && DailyLossHit())
     {
      CloseOurPositionsAfterDailyStop();
      return;
     }
   if(!TradingAuthorized()) return;
   datetime current=iTime(_Symbol,PERIOD_M1,0);
   if(current<=0 || current==g_lastBar) return;
   g_lastBar=current;
   double f[2],s[2],a[1];
   if(CopyBuffer(g_fast,0,1,2,f)!=2 || CopyBuffer(g_slow,0,1,2,s)!=2 || CopyBuffer(g_atr,0,1,1,a)!=1) return;
   // CopyBuffer writes oldest copied bar first: [0] is shift2; [1] is shift1.
   bool crossUp = f[0]<=s[0] && f[1]>s[1];
   bool crossDown = f[0]>=s[0] && f[1]<s[1];
   if(crossUp && (g_policy==TAI_BUY_ONLY || g_policy==TAI_BOTH))
      TryEntry(ORDER_TYPE_BUY,a[0]);
   if(crossDown && (g_policy==TAI_SELL_ONLY || g_policy==TAI_BOTH))
      TryEntry(ORDER_TYPE_SELL,a[0]);
  }
