import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from fastmcp import FastMCP

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

# ── Auth ──────────────────────────────────────────────────────────────────────

REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
API_REGION = os.environ.get("API_REGION", "na")  # na | eu | fe

REGION_ENDPOINTS = {
    "na": "https://advertising-api.amazon.com",
    "eu": "https://advertising-api-eu.amazon.com",
    "fe": "https://advertising-api-fe.amazon.com",
}

_token_cache = {"access_token": None, "expires_at": 0}


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


def headers(profile_id: Optional[str] = None) -> dict:
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


# ── Profiles ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_profiles() -> str:
    """List all Amazon Advertising profiles (accounts) available."""
    r = requests.get(f"{base()}/v2/profiles", headers=headers())
    return ok(r)


@mcp.tool()
def get_profile(profile_id: str) -> str:
    """Get details for a specific profile."""
    r = requests.get(f"{base()}/v2/profiles/{profile_id}", headers=headers())
    return ok(r)


@mcp.tool()
def update_profile(profile_id: str, daily_budget: float) -> str:
    """Update the daily budget of a profile."""
    r = requests.put(
        f"{base()}/v2/profiles",
        headers=headers(),
        json=[{"profileId": int(profile_id), "dailyBudget": daily_budget}],
    )
    return ok(r)


# ── Portfolios ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_portfolios(profile_id: str) -> str:
    """List all portfolios for a profile."""
    r = requests.get(f"{base()}/v1/portfolios", headers=headers(profile_id))
    return ok(r)


@mcp.tool()
def create_portfolio(profile_id: str, name: str, budget_amount: float, budget_currency: str, budget_policy: str = "dateRange", start_date: str = "", end_date: str = "") -> str:
    """Create a new portfolio. budget_policy: dateRange or MonthlyRecurring."""
    body = {"name": name, "budget": {"amount": budget_amount, "currencyCode": budget_currency, "policy": budget_policy}}
    if start_date:
        body["budget"]["startDate"] = start_date
    if end_date:
        body["budget"]["endDate"] = end_date
    r = requests.post(f"{base()}/v1/portfolios", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def update_portfolio(profile_id: str, portfolio_id: str, name: str = "", budget_amount: float = 0) -> str:
    """Update a portfolio name or budget."""
    body = {"portfolioId": int(portfolio_id)}
    if name:
        body["name"] = name
    if budget_amount:
        body["budget"] = {"amount": budget_amount}
    r = requests.put(f"{base()}/v1/portfolios", headers=headers(profile_id), json=[body])
    return ok(r)


# ── Sponsored Products Campaigns ──────────────────────────────────────────────

@mcp.tool()
def list_sp_campaigns(profile_id: str, state_filter: str = "enabled,paused,archived") -> str:
    """List Sponsored Products campaigns. state_filter: enabled,paused,archived"""
    r = requests.get(f"{base()}/v2/sp/campaigns", headers=headers(profile_id), params={"stateFilter": state_filter})
    return ok(r)


@mcp.tool()
def get_sp_campaign(profile_id: str, campaign_id: str) -> str:
    """Get a specific Sponsored Products campaign."""
    r = requests.get(f"{base()}/v2/sp/campaigns/{campaign_id}", headers=headers(profile_id))
    return ok(r)


@mcp.tool()
def create_sp_campaign(profile_id: str, name: str, targeting_type: str, daily_budget: float, start_date: str, end_date: str = "", portfolio_id: str = "") -> str:
    """Create a Sponsored Products campaign. targeting_type: manual or auto. start_date format: YYYYMMDD."""
    body = {
        "name": name,
        "campaignType": "sponsoredProducts",
        "targetingType": targeting_type,
        "state": "enabled",
        "dailyBudget": daily_budget,
        "startDate": start_date,
    }
    if end_date:
        body["endDate"] = end_date
    if portfolio_id:
        body["portfolioId"] = int(portfolio_id)
    r = requests.post(f"{base()}/v2/sp/campaigns", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def update_sp_campaign(profile_id: str, campaign_id: str, name: str = "", state: str = "", daily_budget: float = 0) -> str:
    """Update a Sponsored Products campaign. state: enabled, paused, archived."""
    body = {"campaignId": int(campaign_id)}
    if name:
        body["name"] = name
    if state:
        body["state"] = state
    if daily_budget:
        body["dailyBudget"] = daily_budget
    r = requests.put(f"{base()}/v2/sp/campaigns", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def delete_sp_campaign(profile_id: str, campaign_id: str) -> str:
    """Archive (delete) a Sponsored Products campaign."""
    r = requests.delete(f"{base()}/v2/sp/campaigns/{campaign_id}", headers=headers(profile_id))
    return ok(r)


# ── SP Ad Groups ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_sp_ad_groups(profile_id: str, campaign_id: str = "", state_filter: str = "enabled,paused") -> str:
    """List Sponsored Products ad groups."""
    params = {"stateFilter": state_filter}
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v2/sp/adGroups", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def create_sp_ad_group(profile_id: str, campaign_id: str, name: str, default_bid: float) -> str:
    """Create a Sponsored Products ad group."""
    body = {"campaignId": int(campaign_id), "name": name, "defaultBid": default_bid, "state": "enabled"}
    r = requests.post(f"{base()}/v2/sp/adGroups", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def update_sp_ad_group(profile_id: str, ad_group_id: str, name: str = "", default_bid: float = 0, state: str = "") -> str:
    """Update a Sponsored Products ad group."""
    body = {"adGroupId": int(ad_group_id)}
    if name:
        body["name"] = name
    if default_bid:
        body["defaultBid"] = default_bid
    if state:
        body["state"] = state
    r = requests.put(f"{base()}/v2/sp/adGroups", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def delete_sp_ad_group(profile_id: str, ad_group_id: str) -> str:
    """Archive a Sponsored Products ad group."""
    r = requests.delete(f"{base()}/v2/sp/adGroups/{ad_group_id}", headers=headers(profile_id))
    return ok(r)


# ── SP Keywords ───────────────────────────────────────────────────────────────

@mcp.tool()
def list_sp_keywords(profile_id: str, ad_group_id: str = "", campaign_id: str = "", state_filter: str = "enabled,paused") -> str:
    """List Sponsored Products keywords."""
    params = {"stateFilter": state_filter}
    if ad_group_id:
        params["adGroupIdFilter"] = ad_group_id
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v2/sp/keywords", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def create_sp_keywords(profile_id: str, ad_group_id: str, campaign_id: str, keywords: str, match_type: str = "exact", bid: float = 0.5) -> str:
    """Create SP keywords. keywords: comma-separated list. match_type: exact, phrase, broad."""
    kw_list = [k.strip() for k in keywords.split(",")]
    body = [{"adGroupId": int(ad_group_id), "campaignId": int(campaign_id), "keywordText": kw, "matchType": match_type, "bid": bid, "state": "enabled"} for kw in kw_list]
    r = requests.post(f"{base()}/v2/sp/keywords", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def update_sp_keyword(profile_id: str, keyword_id: str, bid: float = 0, state: str = "") -> str:
    """Update a SP keyword bid or state."""
    body = {"keywordId": int(keyword_id)}
    if bid:
        body["bid"] = bid
    if state:
        body["state"] = state
    r = requests.put(f"{base()}/v2/sp/keywords", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def delete_sp_keyword(profile_id: str, keyword_id: str) -> str:
    """Archive a SP keyword."""
    r = requests.delete(f"{base()}/v2/sp/keywords/{keyword_id}", headers=headers(profile_id))
    return ok(r)


# ── SP Negative Keywords ──────────────────────────────────────────────────────

@mcp.tool()
def list_sp_negative_keywords(profile_id: str, ad_group_id: str = "", campaign_id: str = "") -> str:
    """List Sponsored Products negative keywords."""
    params = {}
    if ad_group_id:
        params["adGroupIdFilter"] = ad_group_id
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v2/sp/negativeKeywords", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def create_sp_negative_keywords(profile_id: str, ad_group_id: str, campaign_id: str, keywords: str, match_type: str = "negativeExact") -> str:
    """Create SP negative keywords. match_type: negativeExact or negativePhrase."""
    kw_list = [k.strip() for k in keywords.split(",")]
    body = [{"adGroupId": int(ad_group_id), "campaignId": int(campaign_id), "keywordText": kw, "matchType": match_type, "state": "enabled"} for kw in kw_list]
    r = requests.post(f"{base()}/v2/sp/negativeKeywords", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def delete_sp_negative_keyword(profile_id: str, keyword_id: str) -> str:
    """Delete a SP negative keyword."""
    r = requests.delete(f"{base()}/v2/sp/negativeKeywords/{keyword_id}", headers=headers(profile_id))
    return ok(r)


# ── SP Product Ads ─────────────────────────────────────────────────────────────

@mcp.tool()
def list_sp_product_ads(profile_id: str, ad_group_id: str = "", campaign_id: str = "", state_filter: str = "enabled,paused") -> str:
    """List Sponsored Products product ads."""
    params = {"stateFilter": state_filter}
    if ad_group_id:
        params["adGroupIdFilter"] = ad_group_id
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v2/sp/productAds", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def create_sp_product_ad(profile_id: str, campaign_id: str, ad_group_id: str, sku: str = "", asin: str = "") -> str:
    """Create a SP product ad. Provide SKU for seller, ASIN for vendor."""
    body = {"campaignId": int(campaign_id), "adGroupId": int(ad_group_id), "state": "enabled"}
    if sku:
        body["sku"] = sku
    if asin:
        body["asin"] = asin
    r = requests.post(f"{base()}/v2/sp/productAds", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def update_sp_product_ad(profile_id: str, ad_id: str, state: str) -> str:
    """Update a SP product ad state: enabled, paused, archived."""
    r = requests.put(f"{base()}/v2/sp/productAds", headers=headers(profile_id), json=[{"adId": int(ad_id), "state": state}])
    return ok(r)


@mcp.tool()
def delete_sp_product_ad(profile_id: str, ad_id: str) -> str:
    """Archive a SP product ad."""
    r = requests.delete(f"{base()}/v2/sp/productAds/{ad_id}", headers=headers(profile_id))
    return ok(r)


# ── SP Targets (Product/Category Targeting) ───────────────────────────────────

@mcp.tool()
def list_sp_targets(profile_id: str, ad_group_id: str = "", campaign_id: str = "", state_filter: str = "enabled,paused") -> str:
    """List SP product/category targeting clauses."""
    params = {"stateFilter": state_filter}
    if ad_group_id:
        params["adGroupIdFilter"] = ad_group_id
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v2/sp/targets", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def create_sp_asin_target(profile_id: str, campaign_id: str, ad_group_id: str, asin: str, bid: float = 0.5) -> str:
    """Create an ASIN product targeting clause for SP."""
    body = [{
        "campaignId": int(campaign_id),
        "adGroupId": int(ad_group_id),
        "state": "enabled",
        "expression": [{"type": "asinSameAs", "value": asin}],
        "expressionType": "manual",
        "bid": bid,
    }]
    r = requests.post(f"{base()}/v2/sp/targets", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def update_sp_target(profile_id: str, target_id: str, bid: float = 0, state: str = "") -> str:
    """Update a SP target bid or state."""
    body = {"targetId": int(target_id)}
    if bid:
        body["bid"] = bid
    if state:
        body["state"] = state
    r = requests.put(f"{base()}/v2/sp/targets", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def delete_sp_target(profile_id: str, target_id: str) -> str:
    """Archive a SP target."""
    r = requests.delete(f"{base()}/v2/sp/targets/{target_id}", headers=headers(profile_id))
    return ok(r)


# ── SP Bid Recommendations ─────────────────────────────────────────────────────

@mcp.tool()
def get_sp_bid_recommendations(profile_id: str, ad_group_id: str, keywords: str) -> str:
    """Get bid recommendations for SP keywords. keywords: comma-separated."""
    kw_list = [{"keyword": k.strip()} for k in keywords.split(",")]
    body = {"adGroupId": int(ad_group_id), "keywords": kw_list}
    r = requests.post(f"{base()}/v2/sp/keywords/bidRecommendations", headers=headers(profile_id), json=body)
    return ok(r)


# ── Sponsored Brands Campaigns ────────────────────────────────────────────────

@mcp.tool()
def list_sb_campaigns(profile_id: str, state_filter: str = "enabled,paused") -> str:
    """List Sponsored Brands campaigns."""
    r = requests.get(f"{base()}/v4/sb/campaigns", headers=headers(profile_id), params={"stateFilter": state_filter})
    return ok(r)


@mcp.tool()
def get_sb_campaign(profile_id: str, campaign_id: str) -> str:
    """Get a specific Sponsored Brands campaign."""
    r = requests.get(f"{base()}/v4/sb/campaigns/{campaign_id}", headers=headers(profile_id))
    return ok(r)


@mcp.tool()
def update_sb_campaign(profile_id: str, campaign_id: str, budget: float = 0, state: str = "", name: str = "") -> str:
    """Update a Sponsored Brands campaign budget, state, or name."""
    body = {"campaignId": campaign_id}
    if budget:
        body["budget"] = {"budget": budget}
    if state:
        body["state"] = state
    if name:
        body["name"] = name
    r = requests.put(f"{base()}/v4/sb/campaigns", headers=headers(profile_id), json={"campaigns": [body]})
    return ok(r)


@mcp.tool()
def list_sb_ad_groups(profile_id: str, campaign_id: str = "") -> str:
    """List Sponsored Brands ad groups."""
    params = {}
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v4/sb/adGroups", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def list_sb_keywords(profile_id: str, campaign_id: str = "", ad_group_id: str = "") -> str:
    """List Sponsored Brands keywords."""
    params = {}
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    if ad_group_id:
        params["adGroupIdFilter"] = ad_group_id
    r = requests.get(f"{base()}/v4/sb/keywords", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def update_sb_keyword(profile_id: str, keyword_id: str, bid: float = 0, state: str = "") -> str:
    """Update a SB keyword bid or state."""
    body = {"keywordId": keyword_id}
    if bid:
        body["bid"] = bid
    if state:
        body["state"] = state
    r = requests.put(f"{base()}/v4/sb/keywords", headers=headers(profile_id), json={"keywords": [body]})
    return ok(r)


@mcp.tool()
def list_sb_negative_keywords(profile_id: str, campaign_id: str = "") -> str:
    """List Sponsored Brands negative keywords."""
    params = {}
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v4/sb/negativeKeywords", headers=headers(profile_id), params=params)
    return ok(r)


# ── Sponsored Display Campaigns ───────────────────────────────────────────────

@mcp.tool()
def list_sd_campaigns(profile_id: str, state_filter: str = "enabled,paused") -> str:
    """List Sponsored Display campaigns."""
    r = requests.get(f"{base()}/sd/campaigns", headers=headers(profile_id), params={"stateFilter": state_filter})
    return ok(r)


@mcp.tool()
def get_sd_campaign(profile_id: str, campaign_id: str) -> str:
    """Get a specific Sponsored Display campaign."""
    r = requests.get(f"{base()}/sd/campaigns/{campaign_id}", headers=headers(profile_id))
    return ok(r)


@mcp.tool()
def update_sd_campaign(profile_id: str, campaign_id: str, budget: float = 0, state: str = "") -> str:
    """Update a Sponsored Display campaign."""
    body = {"campaignId": int(campaign_id)}
    if budget:
        body["budget"] = budget
    if state:
        body["state"] = state
    r = requests.put(f"{base()}/sd/campaigns", headers=headers(profile_id), json=[body])
    return ok(r)


@mcp.tool()
def list_sd_ad_groups(profile_id: str, campaign_id: str = "") -> str:
    """List Sponsored Display ad groups."""
    params = {}
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/sd/adGroups", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def list_sd_targets(profile_id: str, ad_group_id: str = "") -> str:
    """List Sponsored Display targeting clauses."""
    params = {}
    if ad_group_id:
        params["adGroupIdFilter"] = ad_group_id
    r = requests.get(f"{base()}/sd/targets", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def update_sd_target(profile_id: str, target_id: str, bid: float = 0, state: str = "") -> str:
    """Update a SD target bid or state."""
    body = {"targetId": int(target_id)}
    if bid:
        body["bid"] = bid
    if state:
        body["state"] = state
    r = requests.put(f"{base()}/sd/targets", headers=headers(profile_id), json=[body])
    return ok(r)


# ── Reports ───────────────────────────────────────────────────────────────────

@mcp.tool()
def request_sp_campaign_report(profile_id: str, start_date: str, end_date: str, metrics: str = "impressions,clicks,spend,sales7d,acos7d,roas7d,orders7d") -> str:
    """Request a SP campaign performance report. Dates: YYYYMMDD."""
    body = {
        "reportDate": end_date,
        "metrics": metrics,
        "segment": "query",
    }
    r = requests.post(f"{base()}/v2/sp/campaigns/report", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def request_sp_keyword_report(profile_id: str, report_date: str, metrics: str = "impressions,clicks,spend,sales7d,acos7d,roas7d,orders7d,keywordText,matchType") -> str:
    """Request a SP keyword performance report. Date: YYYYMMDD."""
    body = {"reportDate": report_date, "metrics": metrics}
    r = requests.post(f"{base()}/v2/sp/keywords/report", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def request_sp_asin_report(profile_id: str, report_date: str, metrics: str = "impressions,clicks,spend,sales7d,orders7d,asin,advertisedAsin") -> str:
    """Request a SP ASIN (advertised product) report. Date: YYYYMMDD."""
    body = {"reportDate": report_date, "metrics": metrics, "segment": "query"}
    r = requests.post(f"{base()}/v2/sp/productAds/report", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def request_sp_search_term_report(profile_id: str, report_date: str, metrics: str = "impressions,clicks,spend,sales7d,orders7d,keywordText,query,matchType") -> str:
    """Request a SP search term report to see what customers searched. Date: YYYYMMDD."""
    body = {"reportDate": report_date, "metrics": metrics, "segment": "query"}
    r = requests.post(f"{base()}/v2/sp/keywords/report", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def request_sb_campaign_report(profile_id: str, report_date: str, metrics: str = "impressions,clicks,spend,sales14d,orders14d,attributedSales14d") -> str:
    """Request a SB campaign report. Date: YYYYMMDD."""
    body = {"reportDate": report_date, "metrics": metrics}
    r = requests.post(f"{base()}/v4/sb/campaigns/report", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def request_sd_campaign_report(profile_id: str, report_date: str, metrics: str = "impressions,clicks,spend,sales14d,orders14d") -> str:
    """Request a SD campaign report. Date: YYYYMMDD."""
    body = {"reportDate": report_date, "metrics": metrics}
    r = requests.post(f"{base()}/sd/campaigns/report", headers=headers(profile_id), json=body)
    return ok(r)


@mcp.tool()
def get_report_status(profile_id: str, report_id: str) -> str:
    """Check the status of a requested report."""
    r = requests.get(f"{base()}/v2/reports/{report_id}", headers=headers(profile_id))
    return ok(r)


@mcp.tool()
def download_report(profile_id: str, report_id: str) -> str:
    """Download a completed report by reportId. Returns the report data as JSON."""
    status_r = requests.get(f"{base()}/v2/reports/{report_id}", headers=headers(profile_id))
    data = status_r.json()
    if data.get("status") != "SUCCESS":
        return json.dumps({"status": data.get("status"), "message": "Report not ready yet."})
    location = data.get("location")
    if not location:
        return json.dumps({"error": "No download location found."})
    report_r = requests.get(location)
    try:
        return json.dumps(report_r.json(), indent=2)
    except Exception:
        return report_r.text


@mcp.tool()
def get_last_7_days_report_date() -> str:
    """Returns today's date and 7 days ago in YYYYMMDD format for use in reports."""
    today = datetime.utcnow()
    return json.dumps({
        "today": today.strftime("%Y%m%d"),
        "7_days_ago": (today - timedelta(days=7)).strftime("%Y%m%d"),
        "yesterday": (today - timedelta(days=1)).strftime("%Y%m%d"),
    })


# ── Budget Rules ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_budget_rules(profile_id: str, campaign_id: str) -> str:
    """List budget rules for a campaign."""
    r = requests.get(f"{base()}/v1/campaigns/{campaign_id}/budgetRules", headers=headers(profile_id))
    return ok(r)


@mcp.tool()
def create_budget_rule(profile_id: str, campaign_id: str, rule_name: str, budget_increase_by: float, predicate_type: str = "DAYSOFWEEK", predicate_value: str = "MONDAY,TUESDAY,WEDNESDAY,THURSDAY,FRIDAY") -> str:
    """Create a budget rule for a campaign (e.g. increase budget on weekdays)."""
    body = {
        "ruleType": "PERFORMANCE",
        "name": rule_name,
        "budgetIncreasedBy": {"type": "PERCENT", "value": budget_increase_by},
        "conditions": [{"predicate": predicate_type, "value": predicate_value}],
    }
    r = requests.post(f"{base()}/v1/campaigns/{campaign_id}/budgetRules", headers=headers(profile_id), json=body)
    return ok(r)


# ── Suggested Keywords ────────────────────────────────────────────────────────

@mcp.tool()
def get_suggested_keywords_for_asin(profile_id: str, asin: str, ad_group_id: str = "", max_num_suggestions: int = 100) -> str:
    """Get keyword suggestions for an ASIN."""
    params = {"maxNumSuggestions": max_num_suggestions, "adStateFilter": "enabled"}
    if ad_group_id:
        params["adGroupId"] = ad_group_id
    r = requests.get(f"{base()}/v2/sp/asins/{asin}/suggested/keywords", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def get_suggested_keywords_bulk(profile_id: str, asins: str, max_num_suggestions: int = 100) -> str:
    """Get keyword suggestions for multiple ASINs. asins: comma-separated."""
    asin_list = [{"asin": a.strip()} for a in asins.split(",")]
    body = {"asins": asin_list, "maxNumSuggestions": max_num_suggestions}
    r = requests.post(f"{base()}/v2/sp/asins/suggested/keywords", headers=headers(profile_id), json=body)
    return ok(r)


# ── Targeting Recommendations ─────────────────────────────────────────────────

@mcp.tool()
def get_targeting_recommendations(profile_id: str, asins: str) -> str:
    """Get product/category targeting recommendations for ASINs. asins: comma-separated."""
    asin_list = [a.strip() for a in asins.split(",")]
    body = {"asins": asin_list}
    r = requests.post(f"{base()}/v2/sp/targets/productRecommendations", headers=headers(profile_id), json=body)
    return ok(r)


# ── Campaign Negative Keywords ────────────────────────────────────────────────

@mcp.tool()
def list_sp_campaign_negative_keywords(profile_id: str, campaign_id: str = "") -> str:
    """List SP campaign-level negative keywords."""
    params = {}
    if campaign_id:
        params["campaignIdFilter"] = campaign_id
    r = requests.get(f"{base()}/v2/sp/campaignNegativeKeywords", headers=headers(profile_id), params=params)
    return ok(r)


@mcp.tool()
def create_sp_campaign_negative_keyword(profile_id: str, campaign_id: str, keyword: str, match_type: str = "negativeExact") -> str:
    """Add a campaign-level negative keyword to an SP campaign."""
    body = [{"campaignId": int(campaign_id), "keywordText": keyword, "matchType": match_type, "state": "enabled"}]
    r = requests.post(f"{base()}/v2/sp/campaignNegativeKeywords", headers=headers(profile_id), json=body)
    return ok(r)


# ── Health check ──────────────────────────────────────────────────────────────

@mcp.tool()
def health_check() -> str:
    """Check if the MCP server and Amazon Ads API connection are working."""
    try:
        token = get_access_token()
        return json.dumps({"status": "healthy", "token_prefix": token[:20] + "..."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(mcp.http_app(), host="0.0.0.0", port=port)
