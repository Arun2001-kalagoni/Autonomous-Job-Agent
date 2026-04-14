import time
import re
from src.brain import answer_screener_question

def initiate_application(page):
    print("\n   [Form Filler] ⚡ Attempting Easy Apply...")
    
    # 1. Look for the Easy Apply button in the active right pane (not the left card list!)
    # We strictly enforce that the button MUST literally say "Easy", otherwise it's an external Workday Application!
    apply_btn = page.locator("button[data-test='applyButton']:has-text('Easy')").first
    if apply_btn.count() == 0:
        # Fallback if Glassdoor changes datatest: look for a button with Easy Apply specifically inside the details container
        apply_btn = page.locator("[data-job-id] button:has-text('Easy'), header button:has-text('Easy')").first
        
    if apply_btn.count() == 0:
        print("No Easy Apply button found. Skipping.")
        return False
        
    working_page = page
    opened_new_tab = False
    
    try:
        # Set up a listener for a new tab BEFORE we click to perfectly intercept tab creations
        with page.context.expect_page(timeout=4000) as new_page_info:
            apply_btn.click()
            
        # If we got here, a new tab definitely spawned!
        new_page = new_page_info.value
        opened_new_tab = True
        
        try:
            # Wait for the URL to fully resolve from the initial 'about:blank' state
            # CRITICAL: We MUST use wait_for_timeout instead of time.sleep, otherwise we physically block 
            # Playwright's node.js event loop from actually processing the web redirect!
            for _ in range(10):
                if "about:blank" not in new_page.url:
                    break
                new_page.wait_for_timeout(1000)
            new_page.wait_for_load_state("domcontentloaded", timeout=5000)
            new_page.wait_for_timeout(3000) # Give React UI time to actually render the massive form!
        except:
            pass
            
        if "glassdoor.com" in new_page.url or "indeed.com" in new_page.url:
            print("   [Form Filler] 🔄 Easy Apply opened in a new Glassdoor/Indeed tab! Switching context.")
            working_page = new_page
        else:
            print(f"   [Form Filler]  Application redirected to external site ({new_page.url}). Closing tab and skipping.")
            new_page.close()
            return False
            
    except Exception as popup_timeout:
        # A TimeoutError from expect_page just means NO new tab opened, which is perfect! It's a normal modal.
        pass
        
    print("   [Form Filler]  Easy Apply form detected! Navigating...")
    working_page.wait_for_timeout(2000)
    
    steps_completed = 0
    max_steps = 15 # Failsafe to prevent infinite looping
    
    while steps_completed < max_steps:
        # Check if we reached the final "Submit" or "Review" state
        submit_btn = working_page.locator("button:visible:has-text('Submit'), button:visible:has-text('Apply'), input[type='submit']:visible, [data-test='submitButton']:visible").first
        if submit_btn.count() == 0:
            submit_btn = working_page.get_by_role("button", name=re.compile(r"submit|apply", re.IGNORECASE)).first
            
        if submit_btn.count() > 0 and submit_btn.is_visible():
            print("\n   [Form Filler]  REACHED FINAL SUBMIT BUTTON!")
            print("   [Form Filler]  Injecting custom UI control widget into Chrome...")
            
            # Inject a custom floating control panel into the actual Chrome window!
            working_page.evaluate("""
                const widget = document.createElement('div');
                widget.style.position = 'fixed';
                widget.style.top = '20px';
                widget.style.right = '20px';
                widget.style.backgroundColor = 'white';
                widget.style.padding = '20px';
                widget.style.borderRadius = '8px';
                widget.style.border = '4px solid #dc3545';
                widget.style.boxShadow = '0px 10px 30px rgba(0,0,0,0.5)';
                widget.style.zIndex = '9999999';
                widget.innerHTML = '<h3 style="margin-top:0; color:#dc3545;"> AI BOT PAUSED</h3><p>Review the application. You can scroll freely.</p>';
                
                const btnSubmit = document.createElement('button');
                btnSubmit.innerText = ' SUBMIT APPLICATION';
                btnSubmit.style.display = 'block';
                btnSubmit.style.width = '100%';
                btnSubmit.style.margin = '10px 0';
                btnSubmit.style.padding = '10px';
                btnSubmit.style.backgroundColor = '#28a745';
                btnSubmit.style.color = 'white';
                btnSubmit.style.fontSize = '16px';
                btnSubmit.style.cursor = 'pointer';
                
                const btnAbort = document.createElement('button');
                btnAbort.innerText = 'ABORT / SKIP';
                btnAbort.style.display = 'block';
                btnAbort.style.width = '100%';
                btnAbort.style.padding = '10px';
                btnAbort.style.backgroundColor = '#dc3545';
                btnAbort.style.color = 'white';
                btnAbort.style.fontSize = '16px';
                btnAbort.style.cursor = 'pointer';
                
                window.__bot_decision = null;
                btnSubmit.onclick = () => { window.__bot_decision = 'submit'; widget.remove(); };
                btnAbort.onclick = () => { window.__bot_decision = 'abort'; widget.remove(); };
                
                widget.appendChild(btnSubmit);
                widget.appendChild(btnAbort);
                document.body.appendChild(widget);
            """)
            
            print("   [Form Filler]  Waiting indefinitely for you to click the widget in the Chrome Window...")
            
            # Infinite polling loop until the human explicitly clicks one of the injected buttons
            user_decision = None
            while True:
                user_decision = working_page.evaluate("window.__bot_decision")
                if user_decision:
                    break
                working_page.wait_for_timeout(1000)
            
            if user_decision == 'abort':
                print("   [Form Filler]  Aborted application.")
                working_page.keyboard.press("Escape")
                if opened_new_tab: working_page.close()
                return False
                
            submit_btn.first.click(force=True)
            print("   [Form Filler] APPLICATION SUBMITTED! Waiting 15 seconds for the network to finish processing...")
            # We MUST wait so Glassdoor's server database receives the payload before Python closes the socket!
            working_page.wait_for_timeout(15000) 
            if opened_new_tab: working_page.close()
            return True
        
        print(f"   [Form Filler] Scanning questions on step {steps_completed+1}...")
        
        # 2. Extract and Process Questions
        
        # --- Handle Standard `<label>` Inputs and Dropdowns ---
        labels = working_page.locator("label:visible").all()
        for label in labels:
            try:
                question = label.inner_text().strip()
                
                # Skip extremely sensitive or complex uploading fields like Resume
                if any(skip_word in question.lower() for skip_word in ["resume", "cv", "cover letter", "upload"]):
                    continue
                    
                print(f"      Q (Text/Select): {question}")
                
                # Heuristic 1: Find by 'for' ID
                for_attr = label.get_attribute("for")
                input_field = working_page.locator(f"[id='{for_attr}']").first if for_attr else None
                
                # Heuristic 2: Find nested input inside label
                if not input_field or input_field.count() == 0:
                    input_field = label.locator("input:not([type='hidden']), select, textarea").first
                    
                # Heuristic 3: Find adjacent sibling input
                if not input_field or input_field.count() == 0:
                    input_field = label.locator("xpath=following-sibling::*").locator("input:not([type='hidden']), select, textarea").first
                    
                # Heuristic 4: Expand upward to parent container to find detached textareas
                if not input_field or input_field.count() == 0:
                    input_field = label.locator("xpath=..").locator("input:not([type='hidden']), select, textarea").first
                
                if input_field and input_field.count() > 0:
                    tag_name = input_field.evaluate("el => el.tagName").upper()
                    type_attr = input_field.get_attribute("type")
                    
                    if type_attr in ["radio", "checkbox"]:
                        # Extract the true overarching question (usually wrapped in a fieldset or Question container)
                        question_context = question
                        parent_group = label.locator("xpath=ancestor::fieldset | ancestor::div[contains(@class, 'Question') or contains(@class, 'question')]").first
                        if parent_group.count() > 0:
                            question_context = parent_group.inner_text().strip()
                            
                        # Force the RAG AI to evaluate if THIS specific radio option is the correct one!
                        query = f"Context: {question_context} | Is the correct choice strictly '{question}'? Answer Yes or No."
                        ans = answer_screener_question(query, "Yes/No Binary")
                        print(f" Brain evaluates option '{question}': {ans}")
                        
                        # Only mechanically click the dot if the AI verifies it!
                        if "yes" in str(ans).lower():
                            input_field.click(force=True)
                            print(f"Clicked '{question}'!")
                    elif tag_name == "SELECT":
                        optionsText = input_field.evaluate("el => Array.from(el.options).map(o => o.text)")
                        ans = answer_screener_question(question, "Dropdown Options", optionsText)
                        print(f"Brain selects: {ans}")
                        try:
                            input_field.select_option(label=str(ans))
                        except Exception as inner_e:
                            # Fuzzy matching fallback if the LLM drops words
                            for opt in optionsText:
                                if ans.lower() in opt.lower() or opt.lower() in ans.lower():
                                    input_field.select_option(label=opt)
                                    print(f"Fuzzy matched to: {opt}")
                                    break
                    else:
                        ans = answer_screener_question(question, "Text Input")
                        print(f"Brain types: {ans}")
                        input_field.fill(str(ans))
                        # Fire a Tab event to force React Comboboxes/Typeaheads to lock in the typed value!
                        try:
                            input_field.press("Tab")
                        except Exception:
                            pass
                    time.sleep(0.5)
            except Exception as outer_e:
                print(f"DOM Interaction Failed for '{question}': {outer_e}")
                
        # --- Handle `<fieldset>` logic (usually for Radio buttons like Yes/No) ---
        fieldsets = working_page.locator("fieldset:visible").all()
        for fs in fieldsets:
            try:
                legend = fs.locator("legend").first
                if legend.count() > 0:
                    question = legend.inner_text().strip()
                    print(f"      Q (Radio): {question}")
                    
                    # Fetch available radio options text
                    radio_labels = fs.locator("label").all()
                    options = [r.inner_text().strip() for r in radio_labels]
                    
                    ans = answer_screener_question(question, "Radio Options", options)
                    print(f"Brain chooses: {ans}")
                    
                    # Fuzzy match the radio label!
                    target_radio = None
                    for r_text in options:
                        if ans.lower() in r_text.lower() or r_text.lower() in ans.lower():
                            # Extract the exact string verbatim from the DOM for exact matching
                            target_radio = fs.locator("label").filter(has_text=re.compile(re.escape(r_text), re.IGNORECASE)).first
                            break
                            
                    if target_radio and target_radio.count() > 0:
                        target_radio.click(force=True)
                        print(f"Clicked '{ans}' via Fieldset!")
                    else:
                        # Fallback brute force
                        target_radio = fs.locator(f"label:has-text('{ans}')").first
                        if target_radio.count() > 0:
                            target_radio.click(force=True)
                            
                    time.sleep(0.5)
            except Exception as e:
                print(f"Fieldset Radio click failed: {e}")
                
        # 3. Click Continue / Next to proceed to the next modal screen
        # Fallback to get_by_role for perfect accessibility matching, along with standard text matching!
        next_btn = working_page.locator("button:visible:has-text('Continue'), button:visible:has-text('Next'), button:visible:has-text('Review'), [data-test='continueButton']:visible").first
        if next_btn.count() == 0:
            # regex based visible override
            next_btn = working_page.locator("button:visible, [role='button']:visible").filter(has_text=re.compile(r"continue|next|review", re.IGNORECASE)).first
        
        try:
            # Dynamically wait for React to attach the button to the DOM
            next_btn.wait_for(state="attached", timeout=4000)
        except:
            pass
            
        if next_btn.count() > 0 and next_btn.first.is_visible():
            print("   [Form Filler] Pausing for 3.5 seconds so you can visually verify the AI's answers...")
            working_page.wait_for_timeout(3500)
            
            print("   [Form Filler] Clicking Next...")
            next_btn.first.click(force=True)
            working_page.wait_for_timeout(2500) # Give React time to render next page
            steps_completed += 1
        else:
            if submit_btn.count() > 0 and submit_btn.is_visible():
                break # We must have triggered submit at the top
            else:
                # DOM INTROSPECTION DUMP
                all_btn_texts = working_page.locator("button").all_inner_texts()
                print(f"\n   [Form Filler] CRITICAL FAILURE: Cannot find a 'Next' or 'Continue' button on the page!")
                print(f"   I scanned the UI and found these buttons: {all_btn_texts}")
                print(f"   Current URL: {working_page.url}")
                print("   [Form Filler] Aborting application due to broken UI layout.")
            break
            
    # Always exit the modal if we got stuck
    working_page.keyboard.press("Escape")
    if opened_new_tab: working_page.close()
    return False
