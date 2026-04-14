import time
from playwright.sync_api import sync_playwright
from src.automation import get_authenticated_page, search_easy_apply_jobs
from src.brain import evaluate_job_match
from src.database import log_application, init_tracking_db

def run_job_search(job_title="Data Engineer", location="united states", max_age_days=3):
    print(f"\n Starting Auto-Apply Bot for '{job_title}' in '{location}' (Last {max_age_days} days)...")
    
    # Ensure DB is ready
    init_tracking_db()
    
    with sync_playwright() as p:
        try:
            browser, context, page = get_authenticated_page(p, headless=False)
        except Exception as e:
            print(f"Failed to load session: {e}")
            return
            
        print("Session active! Hunting for jobs...")
        
        # 1. Search Glassdoor
        job_cards = search_easy_apply_jobs(page, job_title=job_title, location=location, max_age_days=max_age_days)
        
        if not job_cards:
            print("No job cards found.")
            return

        # 2. Iterate and Evaluate
        for index, card in enumerate(job_cards[:10]): # Limit to first 10 for testing
            try:
                # Glassdoor loves pushing "Sign up for alerts" popups after a few clicks. 
                # Hitting Escape dismisses them so they don't block the screen!
                page.keyboard.press("Escape")
                time.sleep(0.5)
                
                # Scroll to card with a short timeout so it doesn't hang forever if blocked
                try:
                    card.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass # Ignore if it can't scroll, we will force click anyway
                try:
                    card.locator("a[data-test='job-link']").click(force=True, timeout=2000)
                except Exception:
                    card.click(force=True) # Fallback to clicking the whole card
                    
                # Explicitly wait 4 seconds for the Glassdoor XHR backend to fetch the description text
                page.wait_for_timeout(4000) 
                
                # Pull Company Name from the right-pane header (more reliable than the card)
                try:
                    raw_employer_text = page.locator("[data-test='employerName']").inner_text()
                    lines = [line.strip() for line in raw_employer_text.split('\n') if line.strip()]
                    # The actual company name is usually the last item (after the star rating)
                    company = lines[-1] if lines else "Unknown Company"
                except:
                    try:
                        card_lines = card.inner_text().split('\n')
                        # If the first line is exactly a 3 character number like '4.4', skip it
                        if len(card_lines[0]) <= 3 and card_lines[0].replace('.', '', 1).isdigit():
                            company = card_lines[1]
                        else:
                            company = card_lines[0]
                    except:
                        company = "Unknown Company"
                    
                try:
                    title = card.locator("[data-test='job-title']").inner_text()
                except:
                    title = job_title
                    
                try:
                    # Get the actual job link instead of the generic search page URL
                    link = card.locator("a[data-test='job-link']").get_attribute("href")
                    if link and link.startswith('/'):
                        link = "https://www.glassdoor.com" + link
                except:
                    link = page.url + f"#job-{index}"
                
                # Fetch description from right pane (Wait for it specifically!)
                try:
                    page.wait_for_selector(".JobDetails_jobDescription__uW_fK, [data-test='jobDescriptionContent']", timeout=4000)
                    desc_container = page.locator(".JobDetails_jobDescription__uW_fK, [data-test='jobDescriptionContent']").first
                    description = desc_container.inner_text()
                except Exception:
                    # Fallback to grabbing whatever massive text block appeared
                    try:
                        description = page.locator("#JobDescriptionContainer").inner_text()
                    except:
                        description = "Description not found on page layout."

                print(f"\n---------------------------------------------------------")
                print(f"Evaluating Job {index+1}: {title} at {company}")
                
                # 3. Use AI Brain to Score
                evaluation = evaluate_job_match(title, description[:3000]) # Pass first 3K chars to save tokens
                score = evaluation.get("score", 0)
                reasoning = evaluation.get("reasoning", "No reason provided")
                
                print(f"   Match Score: {score}/100")
                if score >= 75:
                    print(f"   GOOD MATCH! Reason:\n      {reasoning}")
                    
                    # 4. Attempt to Automatically Apply!
                    from src.form_filler import initiate_application
                    success = initiate_application(page)
                    
                    status = "APPLY_SUCCESS" if success else "APPLY_ABORTED"
                else:
                    print(f"   POOR MATCH. Reason:\n      {reasoning}")
                    status = "EVALUATED_POOR_MATCH"
                    
                # 4. Log to DB
                log_application(company, title, link, status, score)
                
            except Exception as e:
                print(f"Error processing card {index+1}: {e}")
                
        print("\n Run complete! Check jobs.db for your results.")
        # Provide plenty of time to view before closing
        time.sleep(2)
        browser.close()

if __name__ == "__main__":
    import sys
    print("====================================")
    print("Auto-Job Search Configuration")
    print("====================================")
    
    # Prompt user for filters, defaulting if they just hit Enter
    user_title = input("Target Job Title [Default: Software Developer]: ").strip() or "Software Developer"
    user_location = input("Location (e.g. 'Remote', 'New York') [Default: Remote]: ").strip() or "Remote"
    user_days = input("Max Job Age (1, 3, 7, 14, 30 days) [Default: 3]: ").strip() or "3"
    
    try:
        user_days = int(user_days)
    except ValueError:
        user_days = 3
        
    run_job_search(job_title=user_title, location=user_location, max_age_days=user_days)
