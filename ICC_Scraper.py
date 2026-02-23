import requests
import json
import time
import os
import argparse
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

def parse_duration_to_seconds(duration_str):
    if not duration_str: return None
    try:
        pattern = re.compile(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$', re.IGNORECASE)
        match = pattern.match(duration_str)
        if not match: return None
        hours = float(match.group(1)) if match.group(1) else 0
        minutes = float(match.group(2)) if match.group(2) else 0
        seconds = float(match.group(3)) if match.group(3) else 0
        return hours * 3600 + minutes * 60 + seconds
    except: return None

def extract_extra_field(tags, field_name):
    if not tags: return None
    for tag in tags:
        extra = tag.get('extraData', {})
        if field_name in extra: return extra.get(field_name)
    return None

def get_with_retries(url, retries=5, initial_sleep=5, timeout=10):
    sleep_time = initial_sleep
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except:
            if attempt == retries: return None
            time.sleep(sleep_time)
            sleep_time *= 2

def fetch_and_filter_videos(base_url, language_locale="en-gb", target_video_status_list=None, target_workflow=None, limit_per_request=100, max_skip=None):
    all_filtered_videos = []
    skip = 0
    while True:
        api_url = f"{base_url}/v2/content/{language_locale}/videos?$skip={skip}&$limit={limit_per_request}"
        response = get_with_retries(api_url)
        if response is None: break
        data = response.json()
        items_on_page = data.get('items', [])
        if not items_on_page: break
        for item in items_on_page:
            fields = item.get('fields', {})
            if (target_video_status_list is None or fields.get('videoStatus') in target_video_status_list) and (target_workflow is None or fields.get('workflow') == target_workflow):
                all_filtered_videos.append(item)
        skip += limit_per_request
        if max_skip is not None and skip >= max_skip: break
        time.sleep(2)
    return all_filtered_videos

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-OD", action="store_true")
    args = parser.parse_args()
    BASE_URL = "https://dapi.icc-cricket.com"
    
    if args.OD:
        target_status, max_skip_val, target_wf = ["OnDemand"], 400, None
    else:
        target_status, max_skip_val, target_wf = ["Scheduled", "Live"], 3000, "LIVE"

    videos = fetch_and_filter_videos(BASE_URL, target_video_status_list=target_status, target_workflow=target_wf, max_skip=max_skip_val)
    
    txt_path = "ICC_Events.txt"
    three_months_ago = datetime.now() - timedelta(days=90)
    existing_events = {}

    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    existing_events[line.split("|")[0].strip()] = line.strip()

    for item in videos:
        f = item.get('fields', {})
        eid = str(f.get('videoId'))
        if eid not in existing_events:
            title = item.get('title', 'No Title').replace(":", "")
            existing_events[eid] = f"{eid} | {title} | {f.get('scheduledStartTime')} | {f.get('videoStatus')}"

    final_list = []
    for line in existing_events.values():
        try:
            dt = datetime.fromisoformat(line.split("|")[2].strip().replace('Z', '+00:00'))
            if dt > three_months_ago: final_list.append((dt, line))
        except: final_list.append((datetime.now(), line))

    final_list.sort(key=lambda x: x[0])
    with open(txt_path, "w", encoding="utf-8") as f:
        for _, line in final_list: f.write(line + "\n")
