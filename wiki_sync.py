import pywikibot
import json
import time
from datetime import datetime, timedelta, timezone
import os
import traceback
import paramiko

CONFIG_FILE_PATH = "config.json"

try:
	with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as config_file:
		FTP_CONFIG = json.load(config_file)

except FileNotFoundError:
	print(f"Error: '{CONFIG_FILE_PATH}' bulunamadı")
	exit(1)

LOCAL_JSON_PATH = "veri.json"
TEMP_REMOTE_JSON_PATH = "remote_temp_veri.json"

def fetch_pending_changes_count(site):
	params = {'action': 'query', 'list': 'oldreviewedpages', 'orlimit': '5000', 'format': 'json'}
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
			print(f"Hata (Vikipedi'den veri çekerken): {err}")
			break
	return total_count

def get_data_from_json(file_path):
	if os.path.exists(file_path):
		with open(file_path, 'r', encoding='utf-8') as f:
			try:
				return json.load(f)
			except json.JSONDecodeError:
				return {}
	return {}

def save_data_to_local(data, file_path):
	with open(file_path, 'w', encoding='utf-8') as f:
		json.dump(data, f, ensure_ascii=False, indent=2)

def download_from_sftp():
	try:
		print(f"[{FTP_CONFIG['host']}] veri dosyası alınıyor...")
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh.connect(
			hostname=FTP_CONFIG["host"], 
			port=22, 
			username=FTP_CONFIG["user"], 
			password=FTP_CONFIG["pass"]
		)
		sftp = ssh.open_sftp()
		
		try:
			sftp.stat(FTP_CONFIG["remote_path"]) # File var mı check et
			sftp.get(FTP_CONFIG["remote_path"], TEMP_REMOTE_JSON_PATH)
			print(f"Success:'{TEMP_REMOTE_JSON_PATH}' alındı.")
			success = True
		except IOError:
			print("serverda dosya yok bulunamadı")
			success = False
			
		sftp.close()
		ssh.close()
		return success
	except Exception as err:
		print(f"Warning (Download fail etti): {err}")
		return False

def upload_to_ftp():
	try:
		print(f"[{FTP_CONFIG['host']}] SFTP bağlantı...")
		
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		
		ssh.connect(
			hostname=FTP_CONFIG["host"], 
			port=22, 
			username=FTP_CONFIG["user"], 
			password=FTP_CONFIG["pass"]
		)
		
		sftp = ssh.open_sftp()
		
		remote_dir = os.path.dirname(FTP_CONFIG["remote_path"])
		if remote_dir:
			path_parts = remote_dir.strip('/').split('/')
			current_dir = ''
			for part in path_parts:
				current_dir += '/' + part
				try:
					sftp.stat(current_dir)
				except IOError:
					sftp.mkdir(current_dir)
		
		sftp.put(LOCAL_JSON_PATH, FTP_CONFIG["remote_path"])
		print(f"Success: '{LOCAL_JSON_PATH}' yüklendi")
		
		sftp.close()
		ssh.close()
		
	except Exception as err:
		print("\n" + "="*40)
		traceback.print_exc()
		print("="*40 + "\n")
		print(f"Error: SFTP upload başarısız {err}")

def merge_dictionaries(dict1, dict2):
	merged = dict1.copy()
	for key, value in dict2.items():
		if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
			merged[key] = merge_dictionaries(merged[key], value)
		else:
			merged[key] = value
	return merged

def main():
	try:
		site = pywikibot.Site('tr', 'wikipedia')
		count = fetch_pending_changes_count(site)
		print(f"Anlık bekleyen değişiklik sayısı: {count}")
		local_data = get_data_from_json(LOCAL_JSON_PATH)
		remote_data = {}
		if download_from_sftp():
			remote_data = get_data_from_json(TEMP_REMOTE_JSON_PATH)
			if os.path.exists(TEMP_REMOTE_JSON_PATH):
				os.remove(TEMP_REMOTE_JSON_PATH)
		data = merge_dictionaries(local_data, remote_data)
		now = datetime.now(timezone.utc)
		date_str = now.strftime("%Y-%m-%d")
		hour_str = str(now.hour)
		data.setdefault(date_str, {})[hour_str] = count
		save_data_to_local(data, LOCAL_JSON_PATH)
		print(f"Success: yerel '{LOCAL_JSON_PATH}' içerisine yeni veri eklendi")
		upload_to_ftp()

	except Exception as err:
		print(f"Main function'da hata: {err}")

def run_at_exact_hour():
	while True:
		now = datetime.now(timezone.utc)
		
		if now.minute == 0:
			print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} UTC] Saat başı, işlem başlıyor...")
			main()
			time.sleep(61)
		else:
			seconds_until_next_hour = (60 - now.minute) * 60 - now.second
			print(f"Bir sonraki saat başına {seconds_until_next_hour} saniye var. Bekleniyor...")
			time.sleep(seconds_until_next_hour)

if __name__ == "__main__":
	print("Program başlatıldı, çalıştırılıyor...")
	main()
	print("Saat başı döngüsüne geçiliyor...")
	run_at_exact_hour()
