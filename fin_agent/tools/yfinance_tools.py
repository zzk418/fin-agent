"""
yfinance-based data tools for US stocks and global markets.
Replaces Tushare paid US stock interfaces with free Yahoo Finance data.

Usage: Imported by tushare_tools.py, transparent to the Agent layer.
"""

import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timedelta


def _parse_us_symbol(ts_code: str) -> str:
    """Convert Tushare-style code (AAPL.O) to yfinance ticker (AAPL)."""
    if not ts_code:
        return ts_code
    # Strip Tushare suffixes: .O .N .A etc. Also handle raw tickers
    for suffix in ('.O', '.N', '.A', '.HK'):
        if ts_code.upper().endswith(suffix):
            return ts_code[:-len(suffix)]
    # Handle Chinese stock format (000001.SZ, 600519.SH)
    if '.' in ts_code:
        parts = ts_code.split('.')
        return parts[0]  # Return just the number part
    return ts_code


def get_us_stock_basic(ts_code=None, name=None):
    """
    Get basic information about a US stock via yfinance.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :param name: Stock name for fuzzy search (limited support)
    :return: JSON string
    """
    try:
        if not ts_code and not name:
            return "Error: Please provide ts_code (e.g., 'AAPL') or name."

        symbol = _parse_us_symbol(ts_code) if ts_code else name

        ticker = yf.Ticker(symbol)
        info = ticker.info

        if not info or info.get('trailingPegRatio') is None and not info.get('shortName'):
            return f"Error: Stock '{symbol}' not found or no data available."

        # Build a simple dict with key fields
        result = {
            'ts_code': f"{symbol}.O",
            'symbol': symbol,
            'name': info.get('shortName') or info.get('longName', ''),
            'industry': info.get('industry', ''),
            'sector': info.get('sector', ''),
            'country': info.get('country', ''),
            'market_cap': info.get('marketCap', None),
            'website': info.get('website', ''),
            'fullTimeEmployees': info.get('fullTimeEmployees', None),
            'exchange': info.get('exchange', ''),
            'currency': info.get('currency', 'USD'),
        }
        return json.dumps([result], ensure_ascii=False)

    except Exception as e:
        return f"Error fetching US stock basic info via yfinance: {str(e)}"


def get_us_daily_price(ts_code, start_date=None, end_date=None, adj=None):
    """
    Get historical daily price for a US stock via yfinance.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :param start_date: Start date YYYYMMDD or YYYY-MM-DD
    :param end_date: End date YYYYMMDD or YYYY-MM-DD
    :param adj: Ignored (yfinance always returns adjusted close)
    :return: JSON string
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    else:
        # Convert YYYYMMDD → YYYY-MM-DD
        if len(str(start_date)) == 8:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"

    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    else:
        if len(str(end_date)) == 8:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

    try:
        symbol = _parse_us_symbol(ts_code)
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)

        if df.empty:
            return f"No data found for {symbol} between {start_date} and {end_date}."

        # Reset index so Date becomes a column
        df = df.reset_index()
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        df.rename(columns={
            'Date': 'trade_date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'vol'
        }, inplace=True)
        df['ts_code'] = ts_code

        # Sort descending (most recent first)
        df = df.sort_values('trade_date', ascending=False)

        return df.to_json(orient='records', force_ascii=False)

    except Exception as e:
        return f"Error fetching US daily price via yfinance: {str(e)}"


def get_us_realtime_price(ts_code):
    """
    Get latest/realtime price for a US stock via yfinance.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :return: JSON string
    """
    try:
        symbol = _parse_us_symbol(ts_code)
        ticker = yf.Ticker(symbol)
        info = ticker.info

        if not info:
            return f"No realtime data found for {symbol}."

        # Get latest price from fast_info or info
        try:
            fast = ticker.fast_info
            current_price = fast.get('lastPrice', None) or fast.get('regularMarketPrice', None)
            previous_close = fast.get('previousClose', None) or fast.get('regularMarketPreviousClose', None)
            open_price = fast.get('open', None) or fast.get('regularMarketOpen', None)
            day_high = fast.get('dayHigh', None) or fast.get('regularMarketDayHigh', None)
            day_low = fast.get('dayLow', None) or fast.get('regularMarketDayLow', None)
            volume = fast.get('lastVolume', None) or fast.get('regularMarketVolume', None)
        except Exception:
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
            open_price = info.get('open') or info.get('regularMarketOpen')
            day_high = info.get('dayHigh') or info.get('regularMarketDayHigh')
            day_low = info.get('dayLow') or info.get('regularMarketDayLow')
            volume = info.get('volume') or info.get('regularMarketVolume')

        result = {
            'ts_code': ts_code,
            'name': info.get('shortName') or info.get('longName', symbol),
            'price': current_price or 0,
            'open': open_price or 0,
            'pre_close': previous_close or 0,
            'high': day_high or 0,
            'low': day_low or 0,
            'volume': volume or 0,
            'currency': info.get('currency', 'USD'),
        }

        return json.dumps([result], ensure_ascii=False)

    except Exception as e:
        return f"Error fetching US realtime price via yfinance: {str(e)}"


def get_us_fundamentals(ts_code):
    """
    Get key fundamentals for a US stock via yfinance.
    Returns: PE, PB, ROE, ROA, revenue growth, profit margins, dividend yield, etc.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :return: JSON string
    """
    try:
        symbol = _parse_us_symbol(ts_code)
        ticker = yf.Ticker(symbol)
        info = ticker.info

        if not info:
            return f"No fundamental data found for {symbol}."

        result = {
            'ts_code': ts_code,
            'symbol': symbol,
            'name': info.get('shortName') or info.get('longName', ''),
            # Valuation
            'pe_ttm': info.get('trailingPE'),
            'pe_forward': info.get('forwardPE'),
            'pb': info.get('priceToBook'),
            'ps': info.get('priceToSalesTrailing12Months'),
            'peg_ratio': info.get('pegRatio'),
            # Profitability
            'roe': info.get('returnOnEquity'),
            'roa': info.get('returnOnAssets'),
            'gross_margins': info.get('grossMargins'),
            'operating_margins': info.get('operatingMargins'),
            'profit_margins': info.get('profitMargins'),
            # Growth
            'revenue_growth': info.get('revenueGrowth'),
            'earnings_growth': info.get('earningsGrowth'),
            # Financial health
            'current_ratio': info.get('currentRatio'),
            'quick_ratio': info.get('quickRatio'),
            'debt_to_equity': info.get('debtToEquity'),
            # Returns
            'dividend_yield': info.get('dividendYield'),
            'dividend_rate': info.get('dividendRate'),
            'payout_ratio': info.get('payoutRatio'),
            'beta': info.get('beta'),
            # Size
            'market_cap': info.get('marketCap'),
            'enterprise_value': info.get('enterpriseValue'),
            'revenue': info.get('totalRevenue'),
            'free_cashflow': info.get('freeCashflow'),
            # Price
            'current_price': info.get('currentPrice') or info.get('regularMarketPrice'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            'fifty_day_average': info.get('fiftyDayAverage'),
            'two_hundred_day_average': info.get('twoHundredDayAverage'),
        }
        return json.dumps([result], ensure_ascii=False)

    except Exception as e:
        return f"Error fetching US fundamentals via yfinance: {str(e)}"


def get_us_income_statement(ts_code):
    """
    Get income statement for a US stock via yfinance.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :return: JSON string
    """
    try:
        symbol = _parse_us_symbol(ts_code)
        ticker = yf.Ticker(symbol)
        df = ticker.financials

        if df is None or df.empty:
            return f"No income statement data found for {symbol}."

        df = df.reset_index()
        # Convert column names to strings (they're Timestamps by default)
        df.columns = [str(c)[:10] if hasattr(c, 'strftime') else str(c) for c in df.columns]
        return df.to_json(orient='records', force_ascii=False)

    except Exception as e:
        return f"Error fetching US income statement via yfinance: {str(e)}"


def get_us_balance_sheet(ts_code):
    """
    Get balance sheet for a US stock via yfinance.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :return: JSON string
    """
    try:
        symbol = _parse_us_symbol(ts_code)
        ticker = yf.Ticker(symbol)
        df = ticker.balance_sheet

        if df is None or df.empty:
            return f"No balance sheet data found for {symbol}."

        df = df.reset_index()
        df.columns = [str(c)[:10] if hasattr(c, 'strftime') else str(c) for c in df.columns]
        return df.to_json(orient='records', force_ascii=False)

    except Exception as e:
        return f"Error fetching US balance sheet via yfinance: {str(e)}"


def get_us_cashflow(ts_code):
    """
    Get cashflow statement for a US stock via yfinance.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :return: JSON string
    """
    try:
        symbol = _parse_us_symbol(ts_code)
        ticker = yf.Ticker(symbol)
        df = ticker.cashflow

        if df is None or df.empty:
            return f"No cashflow data found for {symbol}."

        df = df.reset_index()
        df.columns = [str(c)[:10] if hasattr(c, 'strftime') else str(c) for c in df.columns]
        return df.to_json(orient='records', force_ascii=False)

    except Exception as e:
        return f"Error fetching US cashflow via yfinance: {str(e)}"


def get_us_analyst_recommendations(ts_code):
    """
    Get analyst recommendations for a US stock via yfinance.
    :param ts_code: Stock code (e.g., 'AAPL.O' or 'AAPL')
    :return: JSON string
    """
    try:
        symbol = _parse_us_symbol(ts_code)
        ticker = yf.Ticker(symbol)

        # Target price
        info = ticker.info
        target = {
            'current_price': info.get('currentPrice', None),
            'target_mean': info.get('targetMeanPrice', None),
            'target_high': info.get('targetHighPrice', None),
            'target_low': info.get('targetLowPrice', None),
            'recommendation': info.get('recommendationKey', None),
            'number_of_analysts': info.get('numberOfAnalystOpinions', None),
        }
        return json.dumps([target], ensure_ascii=False)

    except Exception as e:
        return f"Error fetching analyst data via yfinance: {str(e)}"


# Schema definitions — only add US stock tools (non-overlapping with existing Tushare tools)
YFINANCE_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_us_stock_basic",
            "description": "Get basic information about a US stock (name, industry, sector, market cap, etc.) via Yahoo Finance. Supports both ticker (e.g., 'AAPL') and Tushare format (e.g., 'AAPL.O'). Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA', 'MSFT'). Also accepts Tushare format ('AAPL.O')."
                    },
                    "name": {
                        "type": "string",
                        "description": "Company name for fuzzy search (e.g., 'Apple Inc')."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_daily_price",
            "description": "Get historical daily OHLCV for a US stock via Yahoo Finance. Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA')."
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYYMMDD format. Defaults to 30 days ago."
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYYMMDD format. Defaults to today."
                    }
                },
                "required": ["ts_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_realtime_price",
            "description": "Get the latest real-time price for a US stock via Yahoo Finance. Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA')."
                    }
                },
                "required": ["ts_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_fundamentals",
            "description": "Get comprehensive fundamental data for a US stock: PE/PB/PS/ROE/ROA, profit margins, growth rates, debt ratios, dividend yield, beta, market cap, 52-week range, etc. All from Yahoo Finance (free).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA')."
                    }
                },
                "required": ["ts_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_income_statement",
            "description": "Get income statement (revenue, expenses, net income) for a US stock via Yahoo Finance. Free.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA')."
                    }
                },
                "required": ["ts_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_balance_sheet",
            "description": "Get balance sheet (assets, liabilities, equity) for a US stock via Yahoo Finance. Free.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA')."
                    }
                },
                "required": ["ts_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_cashflow",
            "description": "Get cashflow statement (operating, investing, financing cash flows) for a US stock via Yahoo Finance. Free.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA')."
                    }
                },
                "required": ["ts_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_analyst_recommendations",
            "description": "Get analyst target prices and consensus recommendation for a US stock via Yahoo Finance. Free.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ts_code": {
                        "type": "string",
                        "description": "The US stock ticker (e.g., 'AAPL', 'NVDA')."
                    }
                },
                "required": ["ts_code"]
            }
        }
    },
]


# Router function — maps tool names to yfinance functions
def execute_yfinance_tool(tool_name, arguments):
    if tool_name == "get_us_stock_basic":
        return get_us_stock_basic(**arguments)
    elif tool_name == "get_us_daily_price":
        return get_us_daily_price(**arguments)
    elif tool_name == "get_us_realtime_price":
        return get_us_realtime_price(**arguments)
    elif tool_name == "get_us_fundamentals":
        return get_us_fundamentals(**arguments)
    elif tool_name == "get_us_income_statement":
        return get_us_income_statement(**arguments)
    elif tool_name == "get_us_balance_sheet":
        return get_us_balance_sheet(**arguments)
    elif tool_name == "get_us_cashflow":
        return get_us_cashflow(**arguments)
    elif tool_name == "get_us_analyst_recommendations":
        return get_us_analyst_recommendations(**arguments)
    else:
        return None  # Not a yfinance tool
