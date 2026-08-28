import json, urllib.request, urllib.parse, os, sys, time, re

QID = "FVWmROVvhgjRPC-4jAUh8A"
LIST_ID = "1812649718805385482"
COOKIE = "auth_token=88ff5a4fef8a1cca75b56243573aaf0c8b248fda; ct0=66bdede7ec536fba2b3f69c9ada717d1a2b07d62b289e269bc15b73b163f81992897f3271625f9a730e82a501d2a40d9d2da780e54f773fc6d49d769433021dbe18f89ddafe062ca162870b14c0f106d; twid=u%3D762241692623900673; guest_id=v1%3A178755903662792207; personalization_id=\"v1_8L6UUqBWh4YhlJD6E9zNcQ==\"; dnt=1"
CT0 = "66bdede7ec536fba2b3f69c9ada717d1a2b07d62b289e269bc15b73b163f81992897f3271625f9a730e82a501d2a40d9d2da780e54f773fc6d49d769433021dbe18f89ddafe062ca162870b14c0f106d"
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

FEATURES = {"rweb_video_screen_enabled":False,"payments_enabled":False,"profile_label_improvements_pcf_label_in_post_enabled":True,"responsive_web_profile_redirect_enabled":False,"rweb_tipjar_consumption_enabled":True,"verified_phone_label_enabled":False,"creator_subscriptions_tweet_preview_api_enabled":True,"responsive_web_graphql_timeline_navigation_enabled":True,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":False,"premium_content_api_read_enabled":False,"communities_web_enable_tweet_community_results_fetch":True,"c9s_tweet_anatomy_moderator_badge_enabled":True,"responsive_web_grok_analyze_button_fetch_trends_enabled":False,"responsive_web_grok_analyze_post_followups_enabled":True,"responsive_web_jetfuel_frame":True,"responsive_web_grok_share_attachment_enabled":True,"articles_preview_enabled":True,"responsive_web_edit_tweet_api_enabled":True,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":True,"view_counts_everywhere_api_enabled":True,"longform_notetweets_consumption_enabled":True,"responsive_web_twitter_article_tweet_consumption_enabled":True,"tweet_awards_web_tipping_enabled":False,"responsive_web_grok_show_grok_translated_post":False,"responsive_web_grok_analysis_button_from_backend":True,"creator_subscriptions_quote_tweet_preview_enabled":False,"freedom_of_speech_not_reach_fetch_enabled":True,"standardized_nudges_misinfo":True,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":True,"longform_notetweets_rich_text_read_enabled":True,"longform_notetweets_inline_media_enabled":True,"responsive_web_grok_image_annotation_enabled":True,"responsive_web_grok_imagine_annotation_enabled":True,"responsive_web_grok_community_note_auto_translation_is_enabled":False,"responsive_web_enhance_cards_enabled":False}

def api_fetch(vars):
    v = urllib.parse.quote(json.dumps(vars))
    f = urllib.parse.quote(json.dumps(FEATURES))
    url = f"https://x.com/i/api/graphql/{QID}/ListLatestTweetsTimeline?variables={v}&features={f}"
    req = urllib.request.Request(url, headers={
        "authorization": "Bearer " + BEARER,
        "cookie": COOKIE,
        "x-csrf-token": CT0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "user-agent": UA,
        "accept": "*/*",
        "origin": "https://x.com",
        "referer": "https://x.com/",
    })
    resp = urllib.request.urlopen(req, timeout=30)
    return resp.status, resp.read().decode("utf-8", "replace")

def extract_tweet(t):
    if not t:
        return None
    tw = t.get("tweet") if t.get("__typename") == "TweetWithVisibilityResults" else t
    if not tw or not tw.get("legacy"):
        return None
    core = tw.get("core", {}).get("user_results", {}).get("result", {})
    # New API: core.user_results.result.core.screen_name
    # Old API: core.user_results.result.legacy.screen_name
    u = core.get("legacy", {}) or core.get("core", {}) or {}
    user_core = core.get("core", {}) or {}
    screen_name = u.get("screen_name", "") or user_core.get("screen_name", "")
    uname = u.get("name", "") or user_core.get("name", "")
    photos = []
    for m in tw.get("extended_entities", {}).get("media", []) or []:
        if m.get("type") == "photo":
            photos.append(m.get("media_url_https", ""))
    if not photos:
        for m in tw.get("legacy", {}).get("entities", {}).get("media", []) or []:
            if m.get("type") == "photo":
                photos.append(m.get("media_url_https", ""))
    return {
        "id": tw["legacy"].get("id_str", ""),
        "at": tw["legacy"].get("created_at", ""),
        "txt": tw["legacy"].get("full_text", ""),
        "user": screen_name,
        "uname": uname,
        "ph": photos,
    }

def main():
    all_tweets = {}
    cursor = None
    now = time.time()
    cutoff = now - 26 * 3600  # 26h window for safety
    for page in range(6):
        vars = {"listId": LIST_ID, "count": 25}
        if cursor:
            vars["cursor"] = cursor
        try:
            status, body = api_fetch(vars)
        except urllib.error.HTTPError as e:
            print("HTTP error:", e.code, e.read()[:300])
            with open("data/tweets.json", "w") as f:
                json.dump({"error": "HTTP " + str(e.code)}, f)
            return
        if status != 200:
            with open("data/tweets.json", "w") as f:
                json.dump({"error": "status " + str(status), "head": body[:300]}, f)
            return
        data = json.loads(body)
        if page == 0:
            with open("data/raw.json", "w") as f:
                f.write(body[:500000])

        # New API structure: data.list.tweets_timeline.timeline.instructions
        tl = data.get("data", {}).get("list", {}).get("tweets_timeline", {})
        if not tl:
            # Old API structure fallback
            tl = data.get("data", {}).get("listLatestTweetsTimeline", {})
        insts = tl.get("timeline", {}).get("instructions", [])
        got = 0
        oldest_seen = None
        for i in insts:
            for e in i.get("entries", []) or []:
                c = e.get("content", {})
                if c.get("entryType") == "TimelineTimelineModule":
                    # Module contains items array
                    for sub in c.get("items", []) or []:
                        t = sub.get("item", {}).get("itemContent", {}).get("tweet_results", {}).get("result")
                        if t:
                            tw = extract_tweet(t)
                            if tw:
                                all_tweets[tw["id"]] = tw
                                got += 1
                elif c.get("entryType") == "TimelineTimelineItem":
                    t = c.get("itemContent", {}).get("tweet_results", {}).get("result")
                    if t:
                        tw = extract_tweet(t)
                        if tw:
                            all_tweets[tw["id"]] = tw
                            got += 1
                if c.get("entryType") == "TimelineTimelineCursor" and c.get("cursorType") == "Bottom":
                    cursor = c.get("value")

        print(f"page {page}: +{got} tweets, cursor={'yes' if cursor else 'none'}")
        if not cursor or got == 0:
            break
        # Stop if all tweets on this page are older than cutoff
        page_tweets = [tw for tw in all_tweets.values() if tw.get("at")]
        if page_tweets:
            # Parse oldest tweet time
            try:
                ts = max(time.mktime(time.strptime(t["at"], "%a %b %d %H:%M:%S +0000 %Y")) for t in page_tweets if t.get("at"))
                if ts < cutoff:
                    print("reached cutoff, stopping")
                    break
            except Exception as ex:
                print("time parse err:", ex)

    # Filter to 24h and remove duplicates by text
    result = []
    seen_texts = set()
    for tw in all_tweets.values():
        try:
            ts = time.mktime(time.strptime(tw["at"], "%a %b %d %H:%M:%S +0000 %Y"))
        except Exception:
            continue
        if now - ts > 24 * 3600 + 1800:
            continue
        # Deduplicate by normalized text
        txt_norm = re.sub(r'\s+', ' ', tw["txt"]).strip().lower()[:150]
        if txt_norm in seen_texts:
            continue
        seen_texts.add(txt_norm)
        tw["ts"] = int(ts)
        result.append(tw)
    result.sort(key=lambda x: -x["ts"])

    with open("data/tweets.json", "w") as f:
        json.dump({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "count": len(result), "tweets": result}, f, ensure_ascii=False, indent=1)
    print("TOTAL:", len(result))

    # Download images
    os.makedirs("data/imgs", exist_ok=True)
    for i, tw in enumerate(result):
        for j, url in enumerate(tw["ph"]):
            fname = f"data/imgs/t{i}_{j}.jpg"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                resp = urllib.request.urlopen(req, timeout=30)
                with open(fname, "wb") as f:
                    f.write(resp.read())
                print(f"img OK {fname}")
            except Exception as e:
                print(f"img FAIL {fname}: {e}")

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    main()
