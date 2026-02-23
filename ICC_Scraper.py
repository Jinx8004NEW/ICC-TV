import requests
import json
import time
import os
import argparse
import re
from urllib.parse import urlparse, parse_qs

def parse_duration_to_seconds(duration_str):
    if not duration_str:
        return None
    try:
        pattern = re.compile(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$', re.IGNORECASE)
        match = pattern.match(duration_str)
        if not match:
            return None
        hours = float(match.group(1)) if match.group(1) else 0
        minutes = float(match.group(2)) if match.group(2) else 0
        seconds = float(match.group(3)) if match.group(3) else 0
        return hours * 3600 + minutes * 60 + seconds
    except Exception:
        return None

def extract_extra_field(tags, field_name):
    if not tags:
        return None
    for tag in tags:
        extra = tag.get('extraData', {})
        if field_name in extra:
            return extra.get(field_name)
    return None

def get_with_retries(url, retries=5, initial_sleep=5, timeout=10):
    sleep_time = initial_sleep
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt == retries:
                return None
            time.sleep(sleep_time)
            sleep_time *= 2

def fetch_and_filter_videos(base_url, language_locale="en-gb", target_video_status_list=None, target_workflow=None, limit_per_request=100, max_skip=None):
    all_filtered_videos = []
    skip = 0
    while True:
        api_url = f"{base_url}/v2/content/{language_locale}/videos?$skip={skip}&$limit={limit_per_request}"
        response = get_with_retries(api_url)
        if response is None:
            break
        data = response.json()
        items_on_page = data.get('items', [])
        if not items_on_page:
            break
        for item in items_on_page:
            fields = item.get('fields', {})
            status = fields.get('videoStatus')
            workflow = fields.get('workflow')
            if fields.get('videoId'):
                if ((target_video_status_list is None or status in target_video_status_list) and 
                    (target_workflow is None or workflow == target_workflow)):
                    all_filtered_videos.append(item)
        skip += limit_per_request
        if max_skip is not None and skip >= max_skip:
            break
        time.sleep(2)
    return all_filtered_videos

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-OD", action="store_true")
    args = parser.parse_args()

    BASE_URL = "https://dapi.icc-cricket.com"
    # Use a consistent filename for the GitHub repo
    json_path = "ICC_Events.json"

    if args.OD:
        target_status, max_skip_value, target_workflow = ["OnDemand"], 400, None
    else:
        target_status, max_skip_value, target_workflow = ["Scheduled", "Live"], 3000, "LIVE"

    videos = fetch_and_filter_videos(BASE_URL, target_video_status_list=target_status, target_workflow=target_workflow, max_skip=max_skip_value)
    
    output_data = []
    for item in videos:
        fields = item.get('fields', {})
        tags = item.get('tags', [])
        untrimmed_seconds = parse_duration_to_seconds(fields.get('untrimmedDuration'))

        if args.OD and (untrimmed_seconds is None or untrimmed_seconds < 600):
            continue

        output_data.append({
            "Title": item.get('title', 'No Title').replace(":", ""),
            "ID": fields.get('videoId'),
            "Status": fields.get('videoStatus'),
            "StartTime": fields.get('scheduledStartTime'),
            "untrimmedDuration": untrimmed_seconds,
            "workflow": fields.get('workflow'),
            "seriesName": extract_extra_field(tags, 'seriesName'),
            "teamA": extract_extra_field(tags, 'teamA'),
            "teamB": extract_extra_field(tags, 'teamB')
        })

    # Persistence Logic: Load existing, merge unique, and save
    existing_data = []
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except:
            existing_data = []

    existing_ids = {str(entry.get("ID")) for entry in existing_data if entry.get("ID")}
    new_entries = [e for e in output_data if str(e.get("ID")) not in existing_ids]
    
    if new_entries:
        merged_data = existing_data + new_entries
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=4)
        print(f"Added {len(new_entries)} new entries.")
    else:
        print("No new unique events found.")
