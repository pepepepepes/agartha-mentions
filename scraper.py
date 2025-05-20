from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import json
import logging
import subprocess
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

YOUR_USERNAME = "AgarthaTerminal"
MENTIONS_FILE = "mentions.json"
PROJECT_DIR = os.path.expandvars(r"%USERPROFILE%\OneDrive\Desktop\x-mentions-bot")

# Ensure working directory is correct
os.chdir(PROJECT_DIR)
logger.info(f"Set working directory to {PROJECT_DIR}")

chrome_options = Options()
# chrome_options.add_argument("--headless")  # Uncomment after login
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

try:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
except Exception as e:
    logger.error(f"Failed to initialize ChromeDriver: {e}")
    exit(1)

def scroll_page():
    last_height = driver.execute_script("return document.body.scrollHeight")
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)
    new_height = driver.execute_script("return document.body.scrollHeight")
    return new_height != last_height

def update_git():
    try:
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True, cwd=PROJECT_DIR)
        if not status.stdout:
            logger.info("No changes to commit")
            return

        # Pull remote changes with rebase
        subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=True, capture_output=True, text=True, cwd=PROJECT_DIR)
        logger.info("Pulled remote changes")

        # Stage changes
        subprocess.run(["git", "add", MENTIONS_FILE], check=True, capture_output=True, text=True, cwd=PROJECT_DIR)
        logger.info("Staged mentions.json")

        # Commit changes
        subprocess.run(["git", "commit", "-m", "Update mentions"], check=True, capture_output=True, text=True, cwd=PROJECT_DIR)
        logger.info("Committed changes")

        # Push to GitHub
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True, text=True, cwd=PROJECT_DIR)
        logger.info("Successfully pushed mentions.json to GitHub")
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error during Git operation: {e}")

def scrape_mentions():
    try:
        driver.get("https://x.com/notifications/mentions")
        logger.info("Navigating to mentions page...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
        )
        for _ in range(5):
            if not scroll_page():
                break
        soup = BeautifulSoup(driver.page_source, "html.parser")
        tweets = soup.find_all("article", role="article")
        logger.info(f"Found {len(tweets)} tweets")
        mentions = []
        for tweet in tweets:
            try:
                text_elem = tweet.find("div", {"lang": True})
                text = text_elem.get_text() if text_elem else "N/A"
                logger.info(f"Tweet text: {text}")
                if YOUR_USERNAME.lower() in text.lower():
                    author_elem = tweet.find("a", {"role": "link", "href": lambda x: x and "/status/" not in x})
                    author = author_elem["href"].split("/")[-1] if author_elem else "Unknown"
                    time_elem = tweet.find("time")
                    timestamp = time_elem["datetime"] if time_elem else time.strftime("%Y-%m-%d %H:%M:%S")
                    mention_data = {
                        "tweet_id": "N/A",
                        "author_id": author,
                        "text": text,
                        "reply_text": "N/A",
                        "timestamp": timestamp
                    }
                    mentions.append(mention_data)
            except Exception as e:
                logger.error(f"Error parsing tweet: {e}")

        if mentions:
            # Load existing mentions to deduplicate
            existing_mentions = set()
            if os.path.exists(MENTIONS_FILE):
                with open(MENTIONS_FILE, "r") as f:
                    for line in f:
                        if line.strip():
                            existing_mentions.add(line.strip())

            # Add new mentions, skipping duplicates
            new_mentions = []
            for mention in mentions:
                mention_str = json.dumps(mention)
                if mention_str not in existing_mentions:
                    new_mentions.append(mention)
                    existing_mentions.add(mention_str)

            if new_mentions:
                with open(MENTIONS_FILE, "a") as f:
                    for mention in new_mentions:
                        json.dump(mention, f)
                        f.write("\n")
                logger.info(f"Saved {len(new_mentions)} new mentions to {MENTIONS_FILE}")
                update_git()
            else:
                logger.info("No new mentions to save after deduplication")
        else:
            logger.info("No new mentions found")
    except Exception as e:
        logger.error(f"Error scraping mentions: {e}")

try:
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    scrape_mentions()
    while True:
        scrape_mentions()
        logger.info("Waiting 300 seconds before next scrape...")
        time.sleep(300)
except KeyboardInterrupt:
    logger.info("Stopping scraper...")
finally:
    driver.quit()