"""
Bu Python betiği, Türkçe Vikipedi'deki bekleyen değişikliklerin anlık sayısını düzenli olarak takip eder.

Ana işlevler:
- Her saat başı, Vikipedi'den bekleyen değişikliklerin güncel sayısını çeker.
- Bu verileri JSON formatında bir kullanıcı alt sayfasında (Kullanıcı:ToprakBot/Bekleyen değişiklikler/data) arşivler.
- Son gün, hafta, ay ve yıl için istatistikleri kullanarak otomatik olarak zaman çizelgesi (timeline) grafikleri üretir.
- Hazırlanan grafik ve özetleri ilgili kullanıcı sayfasına (Kullanıcı:ToprakBot/Bekleyen değişiklikler) kaydeder.
"""
import pywikibot
import json
import time
from datetime import datetime, timedelta, timezone

COLOR_IDS = [
    "green1", "green2", "green3", "green4",
    "yellow1", "orange1", "orange2", "orange3",
    "red1", "red2"
]
COLOR_DEFINITIONS = [
    "  id:green1\tvalue:rgb(0,0.39,0)",
    "  id:green2\tvalue:rgb(0.13,0.39,0)",
    "  id:green3\tvalue:rgb(0.2,0.38,0)",
    "  id:green4\tvalue:rgb(0.24,0.32,0)",
    "  id:yellow1\tvalue:rgb(0.4,0.26,0)",
    "  id:orange1\tvalue:rgb(0.5,0.22,0)",
    "  id:orange2\tvalue:rgb(0.6,0.18,0)",
    "  id:orange3\tvalue:rgb(0.7,0.15,0)",
    "  id:red1\tvalue:rgb(0.8,0.10,0.10)",
    "  id:red2\tvalue:rgb(0.54,0,0)",
]

def fetch_pending_changes_count(site):
    params = {
        'action': 'query',
        'list': 'oldreviewedpages',
        'orlimit': '5000',
        'format': 'json'
    }
    total_count = 0

    while True:
        try:
            data = site.simple_request(**params).submit()
            pages = data.get('query', {}).get('oldreviewedpages', [])
            total_count += len(pages)
            if 'continue' in data:
                params.update(data['continue'])
            else:
                break
        except Exception as err:
            print(f"Error fetching pending changes: {err}")
            break
    return total_count

def update_wiki_page(site, page_title, count):
    try:
        page = pywikibot.Page(site, page_title)
        text = page.text
        data = {}
        if text.strip():
            try:
                data = json.loads(text)
            except json.JSONDecodeError as err:
                print(f"JSON decode error: {err}")
        now = datetime.now(timezone.utc)
        date_str, hour_str = now.strftime("%Y-%m-%d"), now.strftime("%H")
        data.setdefault(date_str, {})[hour_str] = count
        page.text = json.dumps(data, ensure_ascii=False, indent=2)
        page.save(summary=f"Saatlik bekleyen değişiklik sayısı güncellemesi: {count}")
    except Exception as err:
        print(f"Error updating wiki page: {err}")

def read_json_data(site, data_page_title):
    try:
        page = pywikibot.Page(site, data_page_title)
        text = page.text
        return json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        print("Error decoding JSON data")
        return {}
    except Exception as err:
        print(f"Error reading JSON data: {err}")
        return {}

def choose_period_max(max_value):
    thresholds = [500, 1000, 2500, 5000, 10000, 15000]
    for t in thresholds:
        if max_value <= t:
            return t
    return ((max_value + 4999) // 5000) * 5000

def get_color_id(value):
    if value is None or value <= 0:
        return "green1"
    index = int((min(value, 10000) - 500) / (10000 - 500) * (len(COLOR_IDS) - 1))
    return COLOR_IDS[max(0, min(index, len(COLOR_IDS) - 1))]

def get_daily_zero_hour_values(data, start_date, days):
    daily_values = {}
    for i in range(days):
        day = start_date - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        zero_hour_val = data.get(day_str, {}).get("00")
        daily_values[day_str] = zero_hour_val if isinstance(zero_hour_val, int) else 0
    return daily_values

def generate_timeline(data_dict, bar_increment, width, period_type="auto"):
    # data_dict: {label: value}
    values = [v for v in data_dict.values() if isinstance(v, int) and v != 0]
    max_val = max(values, default=0)
    min_val = min(values, default=0) if values else 0

    # Dynamic period, scale_major, scale_minor, width_str calculation
    if period_type == "year":
        # Calculate period range with some margin
        range_margin = int((max_val - min_val) * 0.05) if max_val > min_val else 100
        period_start = ((min_val - range_margin) // 100) * 100
        period_end = ((max_val + range_margin + 99) // 100) * 100
        if period_end == period_start:
            period_end = period_start + 500
        # ScaleMajor and ScaleMinor
        scale_major = max(1, int((period_end - period_start) / 5))
        scale_minor = max(1, int((period_end - period_start) / 25))
        width_str = " width:2"
    else:
        if max_val - min_val <= 100:
            period_start = (min_val // 100) * 100
            period_end = ((max_val + 99) // 100) * 100
            scale_major, scale_minor = 20, 5
        else:
            period_start = (min_val // 100) * 100
            period_end = ((max_val + 99) // 100) * 100
            scale_major = int((period_end - period_start) / 5)
            scale_minor = int((period_end - period_start) / 25)
        width_str = f" width:{width}"

    timeline_lines = [
        "<timeline>",
        "Colors =",
        *COLOR_DEFINITIONS,
        "",
        f"ImageSize = width:auto height:250 barincrement:{bar_increment}",
        "PlotArea = left:50 bottom:20 top:10 right:10",
        "AlignBars = justify",
        "DateFormat=yyyy",
        f"Period = from:{period_start} till:{period_end}",
        "TimeAxis = orientation:vertical",
        f"ScaleMajor=increment:{scale_major} start:{period_start}",
        f"ScaleMinor=increment:{scale_minor} start:{period_start}",
        "PlotData = ",
        width_str
    ]
    # For day: keys are hours ("00") else days ("2025-08-14")
    for label in sorted(data_dict.keys()):
        val = data_dict[label]
        color_id = get_color_id(val)
        timeline_lines.append(f" color:{color_id}")
        # Eğer label bir saat ("00"-"23") formatında ise, ".00" ekle
        if label.isdigit() and len(label) == 2:
            bar_label = f"{label}.00"
        else:
            bar_label = label
        if val is None or val == 0:
            timeline_lines.append(f" bar:{bar_label}")
        else:
            timeline_lines.append(f" bar:{bar_label} from:start till:{val}")
    timeline_lines.append("</timeline>")
    return "\n".join(timeline_lines)

def generate_timeline_for_day(data_for_day):
    # keys: "00", "01", ... "23"
    day_data = {f"{h:02d}": data_for_day.get(f"{h:02d}", 0) for h in range(24)}
    return generate_timeline(day_data, bar_increment=45, width=25, period_type="day")

def generate_timeline_for_week(daily_zero_values):
    return generate_timeline(daily_zero_values, bar_increment=120, width=25, period_type="week")

def generate_timeline_for_month(daily_zero_values):
    return generate_timeline(daily_zero_values, bar_increment=35, width=25, period_type="month")

def generate_timeline_for_year(daily_zero_values):
    return generate_timeline(daily_zero_values, bar_increment=3, width=2, period_type="year")

def save_timeline_page(site, timeline_page_title, timeline_text):
    try:
        page = pywikibot.Page(site, timeline_page_title)
        page.text = timeline_text
        page.save(summary="Bekleyen değişiklikler timeline güncellemesi")
    except Exception as err:
        print(f"Error saving timeline page: {err}")

def main():
    try:
        site = pywikibot.Site('tr', 'wikipedia')
        site.login()

        count = fetch_pending_changes_count(site)
        print(f"Toplam bekleyen değişiklik sayfası sayısı: {count}")

        data_page = "Kullanıcı:ToprakBot/Bekleyen_değişiklikler/data"
        timeline_page = "Kullanıcı:ToprakBot/Bekleyen değişiklikler"
        update_wiki_page(site, data_page, count)

        data = read_json_data(site, data_page)
        now = datetime.now(timezone.utc)
        today_str, yesterday_str = now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")

        # Günlük ve saatlik veriler
        data_today = data.get(today_str, {})
        data_yesterday = data.get(yesterday_str, {})

        # Haftalık, aylık, yıllık veriler
        this_week_data = get_daily_zero_hour_values(data, now, days=7)
        last_week_data = get_daily_zero_hour_values(data, now - timedelta(days=7), days=7)
        this_month_data = get_daily_zero_hour_values(data, now, days=30)
        last_month_data = get_daily_zero_hour_values(data, now - timedelta(days=30), days=30)
        this_year_data = get_daily_zero_hour_values(data, now, days=365)

        timeline_text = (
            "{{/başlık}}\n"
            f"== Bugün ({today_str}) ==\n"
            f"{generate_timeline_for_day(data_today)}\n\n"
            f"== Dün ({yesterday_str}) ==\n"
            f"{generate_timeline_for_day(data_yesterday)}\n\n"
            "== Bu hafta ==\n"
            f"{generate_timeline_for_week(this_week_data)}\n\n"
            "== Geçen hafta ==\n"
            f"{generate_timeline_for_week(last_week_data)}\n\n"
            "== Bu ay ==\n"
            f"{generate_timeline_for_month(this_month_data)}\n\n"
            "== Geçen ay ==\n"
            f"{generate_timeline_for_month(last_month_data)}\n\n"
            "== Son bir yıl ==\n"
            f"{generate_timeline_for_year(this_year_data)}"
        )

        save_timeline_page(site, timeline_page, timeline_text)
    except Exception as err:
        print(f"Main function error: {err}")

def run_at_exact_hour():
    while True:
        now = datetime.now(timezone.utc)
        if now.minute == 0:
            print(f"[{now}] Tam saat başı, main() çalışıyor...")
            try:
                main()
            except Exception as err:
                print(f"Hata oluştu: {err}")
            time.sleep(61)
        else:
            time.sleep(30)

if __name__ == "__main__":
    print("Program başladı, hemen çalıştırılıyor...")
    try:
        main()
    except Exception as e:
        print(f"Hata oluştu: {e}")
    print("Saat başı beklemeye geçiliyor...")
    run_at_exact_hour()