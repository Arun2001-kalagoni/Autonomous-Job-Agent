import os
import time
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import stealth_sync
except ImportError:
    pass # Will be installed by pip shortly

STATE_FILE = "data/state.json"

def setup_glassdoor_session():
    """
    Opens a visible browser for the user to log into Glassdoor manually.
    Once logged in, it saves the session cookies.
    """
    input("Press ENTER when you are ready to log in manually. A browser will open.")
    
    with sync_playwright() as p:
        # Open using actual Chrome + Anti-bot flags
        browser = p.chromium.launch(
            headless=False, 
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        # Spoof a real Mac user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Apply strict stealth patches
        try:
            stealth_sync(page)
        except NameError:
            pass
        
        # Go to Glassdoor
        print("Navigating to Glassdoor...")
        page.goto('https://www.glassdoor.com/')
        
        print("\n PLEASE LOG IN NOW. DO NOT CLOSE THE BROWSER YET.")
        input("ONCE YOU ARE SUCCESSFULLY LOGGED IN, PRESS ENTER IN THIS TERMINAL TO SAVE SESSION...")
        
        print("Login successful! Saving session state...")
        # Save session cookies and storage
        context.storage_state(path=STATE_FILE)
        browser.close()
        print(f"Session saved to {STATE_FILE}. You won't have to log in next time.")

def get_authenticated_page(p, headless=False):
    """
    Returns an authenticated Playwright Context/Page using saved cookies,
    matching the exact stealth signature used during login to prevent Cloudflare blocks.
    """
    if not os.path.exists(STATE_FILE):
        print(f"State file not found. Please run setup first.")
        raise FileNotFoundError(f"Missing {STATE_FILE}")

    # Must match the login browser fingerprint exactly
    browser = p.chromium.launch(
        headless=headless, 
        channel="chrome",
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    # Load the saved session state AND the spoofed User-Agent
    context = browser.new_context(
        storage_state=STATE_FILE,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    page = context.new_page()
    
    # Apply strict stealth patches
    try:
        stealth_sync(page)
    except NameError:
        pass
    
    return browser, context, page

def search_easy_apply_jobs(page, job_title="Software Engineer", location="United States", max_age_days=3):
    """
    Navigates to Glassdoor jobs and searches for positions.
    Returns a list of Playwright Selectors for each job card.
    """
    print(f"Searching for '{job_title}' in '{location}' on Glassdoor (Listed in last {max_age_days} days)...")
    import urllib.parse
    
    base_url = "https://www.glassdoor.com/Job/jobs.htm"
    params = {
        "sc.keyword": job_title,
        "locName": location,
        "fromAge": str(max_age_days), # Filter for age
        "sort.sortType": "RD"         # CRITICAL: Force Glassdoor to sort by "Recent Date" instead of "Relevance"!
    }
    search_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    page.goto(search_url)
    
    # Wait for the right-hand job-list page to appear locally
    try:
        page.wait_for_selector("[data-test='job-list']", timeout=10000)
    except:
        print("Warning: Could not immediately find job list.")
        time.sleep(3)
        
    # Physically interact with the "Date Posted" UI because URL parameters are ignored by React
    print(f"🔄 Clicking 'Date Posted' UI filter to ensure freshness...")
    try:
        # Close any annoying popups before interacting with UI nav bar
        page.keyboard.press("Escape")
        time.sleep(0.5)
        
        # Locate the "Date" filter dropdown button
        date_filter_btn = page.locator("button:has-text('Date'), [data-test='searchFilter-date']").first
        if date_filter_btn.count() > 0:
            date_filter_btn.click(force=True)
            time.sleep(1.5) # Wait for animation
            
            # Map max_age_days to the exact strings the user sees in the Glassdoor UI
            if max_age_days <= 1:
                target_text = "last day"
            elif max_age_days <= 3:
                target_text = "last 3 days"
            elif max_age_days <= 7:
                target_text = "last week"
            elif max_age_days <= 14:
                target_text = "last 2 weeks"
            else:
                target_text = "last month"
                
            # Click the dropdown option that contains our target text (case-insensitive usually handled by Playwright logic)
            option_locator = page.locator(f"li:has-text('{target_text}'), li:has-text('{target_text.capitalize()}'), div[role='option']:has-text('{target_text}'), div[role='option']:has-text('{target_text.capitalize()}')").first
            if option_locator.count() > 0:
                option_locator.click(force=True)
                page.wait_for_timeout(4000) # Give React time to fetch the new fresh list
                print(f"✅ React UI Filter successfully clicked: Last {target_text}")
            else:
                print(f"⚠️ Dropdown option '{target_text}' not found.")
        else:
            print("⚠️ 'Date Posted' filter button not found on screen.")
    except Exception as e:
        print(f"⚠️ Error interacting with Date Posted UI filter: {e}")
        
    # Physically interact with the "Easy Apply" UI toggle
    print(f"🔄 Clicking 'Easy Apply' UI toggle to strictly filter jobs...")
    try:
        # Glassdoor often has a clear button for this near the top
        easy_apply_filter = page.locator("button:has-text('Easy Apply'), [data-test='searchFilter-easyApply'], label[for='EasyApply']").first
        if easy_apply_filter.count() > 0:
            easy_apply_filter.click(force=True)
            page.wait_for_timeout(3000) # Give React time to fetch filtered list
            print(f"✅ React UI Filter successfully clicked: Easy Apply Only")
        else:
            print("⚠️ 'Easy Apply' filter toggle not found on screen.")
    except Exception as e:
        print(f"⚠️ Error interacting with Easy Apply UI filter: {e}")
    
    # Get all the job cards on the left side
    job_cards = page.locator("[data-test='jobListing']").all()
    print(f"Found {len(job_cards)} jobs on the first page.")
    return job_cards

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_glassdoor_session()
    else:
        print("Run 'python src/automation.py setup' to log in.")
