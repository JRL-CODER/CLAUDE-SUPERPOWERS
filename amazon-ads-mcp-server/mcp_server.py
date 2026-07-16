import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Any
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
import uvicorn

# ── Auth ──────────────────────────────────────────────────────────────────────

REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
API_REGION = os.environ.get("API_REGION", "na")

REGION_ENDPOINTS = {
    "na": "https://advertising-api.amazon.com",
    "eu": "https://advertising-api-eu.amazon.com",
    "fe": "https://advertising-api-fe.amazon.com",
}

_token_cache: dict = {"access_token": None, "expires_at": 0}


def get_access_token() -> str:
    now = datetime.utcnow().timestamp()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]
    r = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    r.raise_for_status()
    data = r.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def hdrs(profile_id: Optional[str] = None) -> dict:
    h = {
        "Authorization": f"Bearer {get_access_token()}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Content-Type": "application/json",
    }
    if profile_id:
        h["Amazon-Advertising-API-Scope"] = str(profile_id)
    return h


def base() -> str:
    return REGION_ENDPOINTS.get(API_REGION, REGION_ENDPOINTS["na"])


def ok(r: requests.Response) -> str:
    try:
        return json.dumps(r.json(), indent=2)
    except Exception:
        return r.text


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    # Profiles
    Tool(name="list_profiles", description="List all Amazon Advertising profiles.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_profile", description="Get a specific profile.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="update_profile", description="Update profile daily budget.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "daily_budget": {"type": "number"}}, "required": ["profile_id", "daily_budget"]}),
    # Portfolios
    Tool(name="list_portfolios", description="List portfolios for a profile.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="create_portfolio", description="Create a portfolio.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "name": {"type": "string"}, "budget_amount": {"type": "number"}, "budget_currency": {"type": "string"}}, "required": ["profile_id", "name", "budget_amount", "budget_currency"]}),
    # SP Campaigns
    Tool(name="list_sp_campaigns", description="List Sponsored Products campaigns.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "state_filter": {"type": "string", "default": "enabled,paused,archived"}}, "required": ["profile_id"]}),
    Tool(name="get_sp_campaign", description="Get a specific SP campaign.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id", "campaign_id"]}),
    Tool(name="create_sp_campaign", description="Create an SP campaign. targeting_type: manual or auto. start_date: YYYYMMDD.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "name": {"type": "string"}, "targeting_type": {"type": "string"}, "daily_budget": {"type": "number"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}, "portfolio_id": {"type": "string"}}, "required": ["profile_id", "name", "targeting_type", "daily_budget", "start_date"]}),
    Tool(name="update_sp_campaign", description="Update SP campaign. state: enabled, paused, archived.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "name": {"type": "string"}, "state": {"type": "string"}, "daily_budget": {"type": "number"}}, "required": ["profile_id", "campaign_id"]}),
    Tool(name="delete_sp_campaign", description="Archive an SP campaign.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id", "campaign_id"]}),
    # SP Ad Groups
    Tool(name="list_sp_ad_groups", description="List SP ad groups.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "state_filter": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="create_sp_ad_group", description="Create SP ad group.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "name": {"type": "string"}, "default_bid": {"type": "number"}}, "required": ["profile_id", "campaign_id", "name", "default_bid"]}),
    Tool(name="update_sp_ad_group", description="Update SP ad group.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "name": {"type": "string"}, "default_bid": {"type": "number"}, "state": {"type": "string"}}, "required": ["profile_id", "ad_group_id"]}),
    Tool(name="delete_sp_ad_group", description="Archive SP ad group.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}}, "required": ["profile_id", "ad_group_id"]}),
    # SP Keywords
    Tool(name="list_sp_keywords", description="List SP keywords.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "campaign_id": {"type": "string"}, "state_filter": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="create_sp_keywords", description="Create SP keywords. keywords: comma-separated. match_type: exact, phrase, broad.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "campaign_id": {"type": "string"}, "keywords": {"type": "string"}, "match_type": {"type": "string"}, "bid": {"type": "number"}}, "required": ["profile_id", "ad_group_id", "campaign_id", "keywords"]}),
    Tool(name="update_sp_keyword", description="Update SP keyword bid or state.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "keyword_id": {"type": "string"}, "bid": {"type": "number"}, "state": {"type": "string"}}, "required": ["profile_id", "keyword_id"]}),
    Tool(name="delete_sp_keyword", description="Archive SP keyword.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "keyword_id": {"type": "string"}}, "required": ["profile_id", "keyword_id"]}),
    # SP Negative Keywords
    Tool(name="list_sp_negative_keywords", description="List SP negative keywords.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="create_sp_negative_keywords", description="Create SP negative keywords. match_type: negativeExact or negativePhrase.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "campaign_id": {"type": "string"}, "keywords": {"type": "string"}, "match_type": {"type": "string"}}, "required": ["profile_id", "ad_group_id", "campaign_id", "keywords"]}),
    Tool(name="delete_sp_negative_keyword", description="Delete SP negative keyword.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "keyword_id": {"type": "string"}}, "required": ["profile_id", "keyword_id"]}),
    Tool(name="list_sp_campaign_negative_keywords", description="List SP campaign-level negative keywords.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="create_sp_campaign_negative_keyword", description="Add campaign-level negative keyword.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "keyword": {"type": "string"}, "match_type": {"type": "string"}}, "required": ["profile_id", "campaign_id", "keyword"]}),
    # SP Product Ads
    Tool(name="list_sp_product_ads", description="List SP product ads.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "campaign_id": {"type": "string"}, "state_filter": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="create_sp_product_ad", description="Create SP product ad. Provide SKU for seller or ASIN for vendor.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "sku": {"type": "string"}, "asin": {"type": "string"}}, "required": ["profile_id", "campaign_id", "ad_group_id"]}),
    Tool(name="update_sp_product_ad", description="Update SP product ad state: enabled, paused, archived.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_id": {"type": "string"}, "state": {"type": "string"}}, "required": ["profile_id", "ad_id", "state"]}),
    Tool(name="delete_sp_product_ad", description="Archive SP product ad.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_id": {"type": "string"}}, "required": ["profile_id", "ad_id"]}),
    # SP Targets
    Tool(name="list_sp_targets", description="List SP product/category targeting clauses.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "campaign_id": {"type": "string"}, "state_filter": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="create_sp_asin_target", description="Create ASIN product targeting clause.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "asin": {"type": "string"}, "bid": {"type": "number"}}, "required": ["profile_id", "campaign_id", "ad_group_id", "asin"]}),
    Tool(name="update_sp_target", description="Update SP target bid or state.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "target_id": {"type": "string"}, "bid": {"type": "number"}, "state": {"type": "string"}}, "required": ["profile_id", "target_id"]}),
    Tool(name="delete_sp_target", description="Archive SP target.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "target_id": {"type": "string"}}, "required": ["profile_id", "target_id"]}),
    # SP Recommendations
    Tool(name="get_sp_bid_recommendations", description="Get bid recommendations for SP keywords.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}, "keywords": {"type": "string"}}, "required": ["profile_id", "ad_group_id", "keywords"]}),
    Tool(name="get_suggested_keywords_for_asin", description="Get keyword suggestions for an ASIN.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "asin": {"type": "string"}, "max_num_suggestions": {"type": "integer"}}, "required": ["profile_id", "asin"]}),
    Tool(name="get_suggested_keywords_bulk", description="Get keyword suggestions for multiple ASINs (comma-separated).", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "asins": {"type": "string"}, "max_num_suggestions": {"type": "integer"}}, "required": ["profile_id", "asins"]}),
    Tool(name="get_targeting_recommendations", description="Get targeting recommendations for ASINs (comma-separated).", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "asins": {"type": "string"}}, "required": ["profile_id", "asins"]}),
    # SB Campaigns
    Tool(name="list_sb_campaigns", description="List Sponsored Brands campaigns.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "state_filter": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="get_sb_campaign", description="Get a specific SB campaign.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id", "campaign_id"]}),
    Tool(name="update_sb_campaign", description="Update SB campaign budget, state, or name.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "budget": {"type": "number"}, "state": {"type": "string"}, "name": {"type": "string"}}, "required": ["profile_id", "campaign_id"]}),
    Tool(name="list_sb_ad_groups", description="List SB ad groups.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="list_sb_keywords", description="List SB keywords.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "ad_group_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="update_sb_keyword", description="Update SB keyword bid or state.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "keyword_id": {"type": "string"}, "bid": {"type": "number"}, "state": {"type": "string"}}, "required": ["profile_id", "keyword_id"]}),
    Tool(name="list_sb_negative_keywords", description="List SB negative keywords.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id"]}),
    # SD Campaigns
    Tool(name="list_sd_campaigns", description="List Sponsored Display campaigns.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "state_filter": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="get_sd_campaign", description="Get a specific SD campaign.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id", "campaign_id"]}),
    Tool(name="update_sd_campaign", description="Update SD campaign budget or state.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "budget": {"type": "number"}, "state": {"type": "string"}}, "required": ["profile_id", "campaign_id"]}),
    Tool(name="list_sd_ad_groups", description="List SD ad groups.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="list_sd_targets", description="List SD targeting clauses.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "ad_group_id": {"type": "string"}}, "required": ["profile_id"]}),
    Tool(name="update_sd_target", description="Update SD target bid or state.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "target_id": {"type": "string"}, "bid": {"type": "number"}, "state": {"type": "string"}}, "required": ["profile_id", "target_id"]}),
    # Reports
    Tool(name="request_sp_campaign_report", description="Request SP campaign performance report. Date: YYYYMMDD.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_date": {"type": "string"}, "metrics": {"type": "string"}}, "required": ["profile_id", "report_date"]}),
    Tool(name="request_sp_keyword_report", description="Request SP keyword performance report. Date: YYYYMMDD.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_date": {"type": "string"}, "metrics": {"type": "string"}}, "required": ["profile_id", "report_date"]}),
    Tool(name="request_sp_search_term_report", description="Request SP search term report. Date: YYYYMMDD.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_date": {"type": "string"}, "metrics": {"type": "string"}}, "required": ["profile_id", "report_date"]}),
    Tool(name="request_sp_asin_report", description="Request SP advertised ASIN report. Date: YYYYMMDD.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_date": {"type": "string"}, "metrics": {"type": "string"}}, "required": ["profile_id", "report_date"]}),
    Tool(name="request_sb_campaign_report", description="Request SB campaign report. Date: YYYYMMDD.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_date": {"type": "string"}, "metrics": {"type": "string"}}, "required": ["profile_id", "report_date"]}),
    Tool(name="request_sd_campaign_report", description="Request SD campaign report. Date: YYYYMMDD.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_date": {"type": "string"}, "metrics": {"type": "string"}}, "required": ["profile_id", "report_date"]}),
    Tool(name="get_report_status", description="Check status of a requested report.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_id": {"type": "string"}}, "required": ["profile_id", "report_id"]}),
    Tool(name="download_report", description="Download a completed report by reportId.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "report_id": {"type": "string"}}, "required": ["profile_id", "report_id"]}),
    # Utilities
    Tool(name="get_date_ranges", description="Returns today, yesterday, 7 days ago, 30 days ago in YYYYMMDD format.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="list_budget_rules", description="List budget rules for a campaign.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["profile_id", "campaign_id"]}),
    Tool(name="create_budget_rule", description="Create a budget rule for a campaign.", inputSchema={"type": "object", "properties": {"profile_id": {"type": "string"}, "campaign_id": {"type": "string"}, "rule_name": {"type": "string"}, "budget_increase_by": {"type": "number"}}, "required": ["profile_id", "campaign_id", "rule_name", "budget_increase_by"]}),
    Tool(name="health_check", description="Check if server and Amazon Ads API are working.", inputSchema={"type": "object", "properties": {}}),
]


# ── Tool handlers ─────────────────────────────────────────────────────────────

def handle_tool(name: str, args: dict) -> str:
    p = args.get("profile_id")

    if name == "health_check":
        try:
            token = get_access_token()
            return json.dumps({"status": "healthy", "token_prefix": token[:20] + "..."})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    if name == "get_date_ranges":
        today = datetime.utcnow()
        return json.dumps({"today": today.strftime("%Y%m%d"), "yesterday": (today - timedelta(days=1)).strftime("%Y%m%d"), "7_days_ago": (today - timedelta(days=7)).strftime("%Y%m%d"), "30_days_ago": (today - timedelta(days=30)).strftime("%Y%m%d")})

    if name == "list_profiles":
        return ok(requests.get(f"{base()}/v2/profiles", headers=hdrs()))
    if name == "get_profile":
        return ok(requests.get(f"{base()}/v2/profiles/{args['profile_id']}", headers=hdrs()))
    if name == "update_profile":
        return ok(requests.put(f"{base()}/v2/profiles", headers=hdrs(), json=[{"profileId": int(p), "dailyBudget": args["daily_budget"]}]))

    if name == "list_portfolios":
        return ok(requests.get(f"{base()}/v1/portfolios", headers=hdrs(p)))
    if name == "create_portfolio":
        body = {"name": args["name"], "budget": {"amount": args["budget_amount"], "currencyCode": args["budget_currency"], "policy": args.get("budget_policy", "dateRange")}}
        return ok(requests.post(f"{base()}/v1/portfolios", headers=hdrs(p), json=[body]))

    if name == "list_sp_campaigns":
        return ok(requests.get(f"{base()}/v2/sp/campaigns", headers=hdrs(p), params={"stateFilter": args.get("state_filter", "enabled,paused,archived")}))
    if name == "get_sp_campaign":
        return ok(requests.get(f"{base()}/v2/sp/campaigns/{args['campaign_id']}", headers=hdrs(p)))
    if name == "create_sp_campaign":
        body = {"name": args["name"], "campaignType": "sponsoredProducts", "targetingType": args["targeting_type"], "state": "enabled", "dailyBudget": args["daily_budget"], "startDate": args["start_date"]}
        if args.get("end_date"): body["endDate"] = args["end_date"]
        if args.get("portfolio_id"): body["portfolioId"] = int(args["portfolio_id"])
        return ok(requests.post(f"{base()}/v2/sp/campaigns", headers=hdrs(p), json=[body]))
    if name == "update_sp_campaign":
        body = {"campaignId": int(args["campaign_id"])}
        if args.get("name"): body["name"] = args["name"]
        if args.get("state"): body["state"] = args["state"]
        if args.get("daily_budget"): body["dailyBudget"] = args["daily_budget"]
        return ok(requests.put(f"{base()}/v2/sp/campaigns", headers=hdrs(p), json=[body]))
    if name == "delete_sp_campaign":
        return ok(requests.delete(f"{base()}/v2/sp/campaigns/{args['campaign_id']}", headers=hdrs(p)))

    if name == "list_sp_ad_groups":
        params = {"stateFilter": args.get("state_filter", "enabled,paused")}
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v2/sp/adGroups", headers=hdrs(p), params=params))
    if name == "create_sp_ad_group":
        return ok(requests.post(f"{base()}/v2/sp/adGroups", headers=hdrs(p), json=[{"campaignId": int(args["campaign_id"]), "name": args["name"], "defaultBid": args["default_bid"], "state": "enabled"}]))
    if name == "update_sp_ad_group":
        body = {"adGroupId": int(args["ad_group_id"])}
        if args.get("name"): body["name"] = args["name"]
        if args.get("default_bid"): body["defaultBid"] = args["default_bid"]
        if args.get("state"): body["state"] = args["state"]
        return ok(requests.put(f"{base()}/v2/sp/adGroups", headers=hdrs(p), json=[body]))
    if name == "delete_sp_ad_group":
        return ok(requests.delete(f"{base()}/v2/sp/adGroups/{args['ad_group_id']}", headers=hdrs(p)))

    if name == "list_sp_keywords":
        params = {"stateFilter": args.get("state_filter", "enabled,paused")}
        if args.get("ad_group_id"): params["adGroupIdFilter"] = args["ad_group_id"]
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v2/sp/keywords", headers=hdrs(p), params=params))
    if name == "create_sp_keywords":
        kws = [k.strip() for k in args["keywords"].split(",")]
        body = [{"adGroupId": int(args["ad_group_id"]), "campaignId": int(args["campaign_id"]), "keywordText": kw, "matchType": args.get("match_type", "exact"), "bid": args.get("bid", 0.5), "state": "enabled"} for kw in kws]
        return ok(requests.post(f"{base()}/v2/sp/keywords", headers=hdrs(p), json=body))
    if name == "update_sp_keyword":
        body = {"keywordId": int(args["keyword_id"])}
        if args.get("bid"): body["bid"] = args["bid"]
        if args.get("state"): body["state"] = args["state"]
        return ok(requests.put(f"{base()}/v2/sp/keywords", headers=hdrs(p), json=[body]))
    if name == "delete_sp_keyword":
        return ok(requests.delete(f"{base()}/v2/sp/keywords/{args['keyword_id']}", headers=hdrs(p)))

    if name == "list_sp_negative_keywords":
        params = {}
        if args.get("ad_group_id"): params["adGroupIdFilter"] = args["ad_group_id"]
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v2/sp/negativeKeywords", headers=hdrs(p), params=params))
    if name == "create_sp_negative_keywords":
        kws = [k.strip() for k in args["keywords"].split(",")]
        body = [{"adGroupId": int(args["ad_group_id"]), "campaignId": int(args["campaign_id"]), "keywordText": kw, "matchType": args.get("match_type", "negativeExact"), "state": "enabled"} for kw in kws]
        return ok(requests.post(f"{base()}/v2/sp/negativeKeywords", headers=hdrs(p), json=body))
    if name == "delete_sp_negative_keyword":
        return ok(requests.delete(f"{base()}/v2/sp/negativeKeywords/{args['keyword_id']}", headers=hdrs(p)))
    if name == "list_sp_campaign_negative_keywords":
        params = {}
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v2/sp/campaignNegativeKeywords", headers=hdrs(p), params=params))
    if name == "create_sp_campaign_negative_keyword":
        return ok(requests.post(f"{base()}/v2/sp/campaignNegativeKeywords", headers=hdrs(p), json=[{"campaignId": int(args["campaign_id"]), "keywordText": args["keyword"], "matchType": args.get("match_type", "negativeExact"), "state": "enabled"}]))

    if name == "list_sp_product_ads":
        params = {"stateFilter": args.get("state_filter", "enabled,paused")}
        if args.get("ad_group_id"): params["adGroupIdFilter"] = args["ad_group_id"]
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v2/sp/productAds", headers=hdrs(p), params=params))
    if name == "create_sp_product_ad":
        body = {"campaignId": int(args["campaign_id"]), "adGroupId": int(args["ad_group_id"]), "state": "enabled"}
        if args.get("sku"): body["sku"] = args["sku"]
        if args.get("asin"): body["asin"] = args["asin"]
        return ok(requests.post(f"{base()}/v2/sp/productAds", headers=hdrs(p), json=[body]))
    if name == "update_sp_product_ad":
        return ok(requests.put(f"{base()}/v2/sp/productAds", headers=hdrs(p), json=[{"adId": int(args["ad_id"]), "state": args["state"]}]))
    if name == "delete_sp_product_ad":
        return ok(requests.delete(f"{base()}/v2/sp/productAds/{args['ad_id']}", headers=hdrs(p)))

    if name == "list_sp_targets":
        params = {"stateFilter": args.get("state_filter", "enabled,paused")}
        if args.get("ad_group_id"): params["adGroupIdFilter"] = args["ad_group_id"]
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v2/sp/targets", headers=hdrs(p), params=params))
    if name == "create_sp_asin_target":
        body = [{"campaignId": int(args["campaign_id"]), "adGroupId": int(args["ad_group_id"]), "state": "enabled", "expression": [{"type": "asinSameAs", "value": args["asin"]}], "expressionType": "manual", "bid": args.get("bid", 0.5)}]
        return ok(requests.post(f"{base()}/v2/sp/targets", headers=hdrs(p), json=body))
    if name == "update_sp_target":
        body = {"targetId": int(args["target_id"])}
        if args.get("bid"): body["bid"] = args["bid"]
        if args.get("state"): body["state"] = args["state"]
        return ok(requests.put(f"{base()}/v2/sp/targets", headers=hdrs(p), json=[body]))
    if name == "delete_sp_target":
        return ok(requests.delete(f"{base()}/v2/sp/targets/{args['target_id']}", headers=hdrs(p)))

    if name == "get_sp_bid_recommendations":
        kws = [{"keyword": k.strip()} for k in args["keywords"].split(",")]
        return ok(requests.post(f"{base()}/v2/sp/keywords/bidRecommendations", headers=hdrs(p), json={"adGroupId": int(args["ad_group_id"]), "keywords": kws}))
    if name == "get_suggested_keywords_for_asin":
        params = {"maxNumSuggestions": args.get("max_num_suggestions", 100), "adStateFilter": "enabled"}
        return ok(requests.get(f"{base()}/v2/sp/asins/{args['asin']}/suggested/keywords", headers=hdrs(p), params=params))
    if name == "get_suggested_keywords_bulk":
        asin_list = [{"asin": a.strip()} for a in args["asins"].split(",")]
        return ok(requests.post(f"{base()}/v2/sp/asins/suggested/keywords", headers=hdrs(p), json={"asins": asin_list, "maxNumSuggestions": args.get("max_num_suggestions", 100)}))
    if name == "get_targeting_recommendations":
        return ok(requests.post(f"{base()}/v2/sp/targets/productRecommendations", headers=hdrs(p), json={"asins": [a.strip() for a in args["asins"].split(",")]}))

    if name == "list_sb_campaigns":
        return ok(requests.get(f"{base()}/v4/sb/campaigns", headers=hdrs(p), params={"stateFilter": args.get("state_filter", "enabled,paused")}))
    if name == "get_sb_campaign":
        return ok(requests.get(f"{base()}/v4/sb/campaigns/{args['campaign_id']}", headers=hdrs(p)))
    if name == "update_sb_campaign":
        body = {"campaignId": args["campaign_id"]}
        if args.get("budget"): body["budget"] = {"budget": args["budget"]}
        if args.get("state"): body["state"] = args["state"]
        if args.get("name"): body["name"] = args["name"]
        return ok(requests.put(f"{base()}/v4/sb/campaigns", headers=hdrs(p), json={"campaigns": [body]}))
    if name == "list_sb_ad_groups":
        params = {}
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v4/sb/adGroups", headers=hdrs(p), params=params))
    if name == "list_sb_keywords":
        params = {}
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        if args.get("ad_group_id"): params["adGroupIdFilter"] = args["ad_group_id"]
        return ok(requests.get(f"{base()}/v4/sb/keywords", headers=hdrs(p), params=params))
    if name == "update_sb_keyword":
        body = {"keywordId": args["keyword_id"]}
        if args.get("bid"): body["bid"] = args["bid"]
        if args.get("state"): body["state"] = args["state"]
        return ok(requests.put(f"{base()}/v4/sb/keywords", headers=hdrs(p), json={"keywords": [body]}))
    if name == "list_sb_negative_keywords":
        params = {}
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/v4/sb/negativeKeywords", headers=hdrs(p), params=params))

    if name == "list_sd_campaigns":
        return ok(requests.get(f"{base()}/sd/campaigns", headers=hdrs(p), params={"stateFilter": args.get("state_filter", "enabled,paused")}))
    if name == "get_sd_campaign":
        return ok(requests.get(f"{base()}/sd/campaigns/{args['campaign_id']}", headers=hdrs(p)))
    if name == "update_sd_campaign":
        body = {"campaignId": int(args["campaign_id"])}
        if args.get("budget"): body["budget"] = args["budget"]
        if args.get("state"): body["state"] = args["state"]
        return ok(requests.put(f"{base()}/sd/campaigns", headers=hdrs(p), json=[body]))
    if name == "list_sd_ad_groups":
        params = {}
        if args.get("campaign_id"): params["campaignIdFilter"] = args["campaign_id"]
        return ok(requests.get(f"{base()}/sd/adGroups", headers=hdrs(p), params=params))
    if name == "list_sd_targets":
        params = {}
        if args.get("ad_group_id"): params["adGroupIdFilter"] = args["ad_group_id"]
        return ok(requests.get(f"{base()}/sd/targets", headers=hdrs(p), params=params))
    if name == "update_sd_target":
        body = {"targetId": int(args["target_id"])}
        if args.get("bid"): body["bid"] = args["bid"]
        if args.get("state"): body["state"] = args["state"]
        return ok(requests.put(f"{base()}/sd/targets", headers=hdrs(p), json=[body]))

    if name == "request_sp_campaign_report":
        return ok(requests.post(f"{base()}/v2/sp/campaigns/report", headers=hdrs(p), json={"reportDate": args["report_date"], "metrics": args.get("metrics", "impressions,clicks,spend,sales7d,acos7d,roas7d,orders7d")}))
    if name == "request_sp_keyword_report":
        return ok(requests.post(f"{base()}/v2/sp/keywords/report", headers=hdrs(p), json={"reportDate": args["report_date"], "metrics": args.get("metrics", "impressions,clicks,spend,sales7d,acos7d,roas7d,orders7d,keywordText,matchType")}))
    if name == "request_sp_search_term_report":
        return ok(requests.post(f"{base()}/v2/sp/keywords/report", headers=hdrs(p), json={"reportDate": args["report_date"], "metrics": args.get("metrics", "impressions,clicks,spend,sales7d,orders7d,keywordText,query,matchType"), "segment": "query"}))
    if name == "request_sp_asin_report":
        return ok(requests.post(f"{base()}/v2/sp/productAds/report", headers=hdrs(p), json={"reportDate": args["report_date"], "metrics": args.get("metrics", "impressions,clicks,spend,sales7d,orders7d,asin,advertisedAsin")}))
    if name == "request_sb_campaign_report":
        return ok(requests.post(f"{base()}/v4/sb/campaigns/report", headers=hdrs(p), json={"reportDate": args["report_date"], "metrics": args.get("metrics", "impressions,clicks,spend,sales14d,orders14d")}))
    if name == "request_sd_campaign_report":
        return ok(requests.post(f"{base()}/sd/campaigns/report", headers=hdrs(p), json={"reportDate": args["report_date"], "metrics": args.get("metrics", "impressions,clicks,spend,sales14d,orders14d")}))
    if name == "get_report_status":
        return ok(requests.get(f"{base()}/v2/reports/{args['report_id']}", headers=hdrs(p)))
    if name == "download_report":
        r = requests.get(f"{base()}/v2/reports/{args['report_id']}", headers=hdrs(p))
        data = r.json()
        if data.get("status") != "SUCCESS":
            return json.dumps({"status": data.get("status"), "message": "Report not ready yet."})
        location = data.get("location")
        if not location:
            return json.dumps({"error": "No download location."})
        rr = requests.get(location)
        try:
            return json.dumps(rr.json(), indent=2)
        except Exception:
            return rr.text

    if name == "list_budget_rules":
        return ok(requests.get(f"{base()}/v1/campaigns/{args['campaign_id']}/budgetRules", headers=hdrs(p)))
    if name == "create_budget_rule":
        body = {"ruleType": "PERFORMANCE", "name": args["rule_name"], "budgetIncreasedBy": {"type": "PERCENT", "value": args["budget_increase_by"]}, "conditions": [{"predicate": args.get("predicate_type", "DAYSOFWEEK"), "value": args.get("predicate_value", "MONDAY,TUESDAY,WEDNESDAY,THURSDAY,FRIDAY")}]}
        return ok(requests.post(f"{base()}/v1/campaigns/{args['campaign_id']}/budgetRules", headers=hdrs(p), json=body))

    return json.dumps({"error": f"Unknown tool: {name}"})


# ── MCP Server ────────────────────────────────────────────────────────────────

server = Server("che-mate-ads-mcp")


@server.list_tools()
async def list_tools():
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = handle_tool(name, arguments)
    return [TextContent(type="text", text=result)]


# ── Starlette app ─────────────────────────────────────────────────────────────

sse = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
