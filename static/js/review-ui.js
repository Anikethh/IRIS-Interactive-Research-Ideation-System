/**
 * Review UI Component
 * Handles displaying review boxes for each aspect and highlighting text
 */
class ReviewUI {
  constructor() {
    console.log('ReviewUI: Creating new instance');
    this.reviews = {};
    this.acceptedReviews = [];
    this.rejectedReviews = [];
    this.activeAspect = null;
    this.initialized = false;
    this.callbacks = {};
    // Track total expected aspects - will be populated from backend
    this.expectedAspects = [];
    // Minimum number of aspects to accept for improvement
    this.minAcceptedReviews = 3;
  }
  
  /**
   * Initialize the review UI
   */
  init() {
    console.log(`ReviewUI: Initializing`);
    this.initialized = true;
    console.log('ReviewUI: Initialization complete');
  }
  
  /**
   * Add or update a review - now inserts into chat flow
   * @param {string} aspect - The review aspect (novelty, feasibility, etc)
   * @param {Object} data - The review data
   */
  addReview(aspect, data) {
    console.log(`ReviewUI: Adding/updating review for ${aspect}`, data);
    
    if (!this.initialized) {
      console.log('ReviewUI: Initializing before adding review');
      this.init();
    }
    
    // Add aspect to expected aspects if not already there
    if (!this.expectedAspects.includes(aspect)) {
      this.expectedAspects.push(aspect);
    }
    
    this.reviews[aspect] = data;
    console.log(`ReviewUI: Stored review data for ${aspect}`);
    
    // Create review element to insert into chat
    const reviewElement = document.createElement('div');
    reviewElement.id = `review-box-${aspect}`;
    reviewElement.className = 'review-card collapsed'; // Start collapsed
    reviewElement.setAttribute('data-aspect', aspect);
    
    // Get color for the aspect - Using similar colors to highlight styles
    const aspectColors = {
      'novelty': 'rgba(253, 224, 71, 0.4)',
      'feasibility': 'rgba(134, 239, 172, 0.4)',
      'clarity': 'rgba(147, 197, 253, 0.4)',
      'impact': 'rgba(216, 180, 254, 0.4)',
      'methodology': 'rgba(251, 146, 60, 0.4)',
      'lack_of_novelty': 'rgba(253, 224, 71, 0.4)',
      'assumptions': 'rgba(134, 239, 172, 0.4)',
      'vagueness': 'rgba(147, 197, 253, 0.4)',
      'feasibility_and_practicality': 'rgba(216, 180, 254, 0.4)',
      'overgeneralization': 'rgba(251, 146, 60, 0.4)',
      'overstatement': 'rgba(99, 102, 241, 0.4)',
      'evaluation_and_validation_issues': 'rgba(244, 114, 182, 0.4)',
      'justification_for_methods': 'rgba(20, 184, 166, 0.4)',
      'reproducibility': 'rgba(168, 85, 247, 0.4)',
      'contradictory_statements': 'rgba(239, 68, 68, 0.4)',
      'alignment': 'rgba(16, 185, 129, 0.4)',
      'ethical_and_social_considerations': 'rgba(59, 130, 246, 0.4)',
      'robustness': 'rgba(236, 72, 153, 0.4)'
    };
    
    const aspectColor = aspectColors[aspect] || 'rgba(148, 163, 184, 0.2)'; // Default gray if aspect not found
    
    // Create header that's always visible with improved structure
    const header = document.createElement('div');
    header.className = 'review-card-header';
    
    // Create the aspect name element
    const aspectNameEl = document.createElement('div');
    aspectNameEl.className = 'aspect-name';
    aspectNameEl.textContent = aspect.replace(/_/g, ' '); // Replace underscores with spaces for display
    
    // Create a container for the right side elements (score and toggle)
    const headerRight = document.createElement('div');
    headerRight.className = 'review-card-header-right';
    
    // Create score element with the background color matching the highlight
    const scoreEl = document.createElement('div');
    scoreEl.className = 'aspect-score';
    scoreEl.textContent = `${data.score}/10`;
    scoreEl.style.backgroundColor = aspectColor;
    scoreEl.style.color = '#334155'; // Darker text for better readability
    
    // Create toggle element
    const toggleEl = document.createElement('div');
    toggleEl.className = 'expand-toggle';
    toggleEl.innerHTML = '<span class="expand-icon">▼</span>';
    
    // Assemble the header
    header.appendChild(aspectNameEl);
    headerRight.appendChild(scoreEl);
    headerRight.appendChild(toggleEl);
    header.appendChild(headerRight);
    
    // Create body that's hidden by default
    const body = document.createElement('div');
    body.className = 'review-card-body';
    body.style.display = 'none'; // Hidden by default
    body.innerHTML = `
      <div class="review-summary">${data.summary}</div>
      ${data.highlight ? `
        <div class="highlight-section">
          <div class="highlight-category">${data.highlight.category}</div>
          <div class="highlight-text">"${data.highlight.text}"</div>
          <div class="highlight-review">${data.highlight.review}</div>
        </div>
      ` : ''}
    `;
    
    // Create actions section
    const actions = document.createElement('div');
    actions.className = 'review-card-actions';
    actions.style.display = 'none'; // Hidden by default
    actions.innerHTML = `
      <button class="accept-btn" title="Accept this feedback">
        <img src="/static/icons/tick.svg" alt="Accept" width="16" height="16">
      </button>
      <button class="reject-btn" title="Reject this feedback">
        <img src="/static/icons/cross.svg" alt="Reject" width="16" height="16">
      </button>
    `;
    
    // Add click handlers
    const acceptBtn = actions.querySelector('.accept-btn');
    const rejectBtn = actions.querySelector('.reject-btn');
    
    acceptBtn.addEventListener('click', () => this.acceptReview(aspect));
    rejectBtn.addEventListener('click', () => this.rejectReview(aspect));
    
    // Add click handler for expand/collapse toggle
    header.addEventListener('click', () => {
      const isCollapsed = reviewElement.classList.contains('collapsed');
      
      if (isCollapsed) {
        // Expand
        reviewElement.classList.remove('collapsed');
        reviewElement.classList.add('expanded');
        body.style.display = 'block';
        actions.style.display = 'flex';
        header.querySelector('.expand-icon').textContent = '▲';
      } else {
        // Collapse
        reviewElement.classList.add('collapsed');
        reviewElement.classList.remove('expanded');
        body.style.display = 'none';
        actions.style.display = 'none';
        header.querySelector('.expand-icon').textContent = '▼';
      }
    });
    
    // Add elements to review card
    reviewElement.appendChild(header);
    reviewElement.appendChild(body);
    reviewElement.appendChild(actions);
    
    // Insert the review into the chat area
    const chatArea = document.getElementById('chat-box');
    if (chatArea) {
      // Create wrapper with system sender attribute for proper styling
      const wrapper = document.createElement('div');
      wrapper.setAttribute('data-sender', 'system');
      wrapper.className = 'review-message-container';
      wrapper.appendChild(reviewElement);
      
      chatArea.appendChild(wrapper);
      
      // Scroll to the new review
      // chatArea.scrollTop = chatArea.scrollHeight;
      
      // Highlight text in the main idea if applicable
      if (data.highlight && data.highlight.text) {
        this.highlightText(aspect);
      }
      
      // Only show improve button after the last aspect (robustness)
      if (aspect === 'robustness') {
        setTimeout(() => {
          this.showImproveIdeaButton();
        }, 1000); // Small delay to ensure all UI updates are complete
      }
    } else {
      console.error('ReviewUI: Chat area not found');
    }
    
    return reviewElement;
  }
  
  /**
   * Accept a review suggestion
   * @param {string} aspect - The aspect being accepted
   */
  acceptReview(aspect) {
    console.log(`ReviewUI: Accepting review for ${aspect}`);
    
    const review = this.reviews[aspect];
    if (!review) {
      console.error(`ReviewUI: No review found for aspect ${aspect}`);
      return;
    }
    
    // Add to accepted reviews if not already there
    if (!this.acceptedReviews.includes(aspect)) {
      this.acceptedReviews.push(aspect);
      
      // Remove from rejected if it was there
      const rejectedIndex = this.rejectedReviews.indexOf(aspect);
      if (rejectedIndex > -1) {
        this.rejectedReviews.splice(rejectedIndex, 1);
      }
    }
    
    // Update UI to show it's accepted
    const reviewElement = document.getElementById(`review-box-${aspect}`);
    if (reviewElement) {
      // Add visual indicator that it's accepted
      reviewElement.classList.add('accepted');
      reviewElement.classList.remove('rejected');
    }
    
    // Check if all reviews are complete (either accepted or rejected)
    this.checkReviewsComplete();
  }
  
  /**
   * Reject a review suggestion
   * @param {string} aspect - The aspect being rejected
   */
  rejectReview(aspect) {
    console.log(`ReviewUI: Rejecting review for ${aspect}`);
    
    const review = this.reviews[aspect];
    if (!review) {
      console.error(`ReviewUI: No review found for aspect ${aspect}`);
      return;
    }
    
    // Add to rejected reviews if not already there
    if (!this.rejectedReviews.includes(aspect)) {
      this.rejectedReviews.push(aspect);
      
      // Remove from accepted if it was there
      const acceptedIndex = this.acceptedReviews.indexOf(aspect);
      if (acceptedIndex > -1) {
        this.acceptedReviews.splice(acceptedIndex, 1);
      }
    }
    
    // Update UI to show it's rejected
    const reviewElement = document.getElementById(`review-box-${aspect}`);
    if (reviewElement) {
      // Add visual indicator that it's rejected
      reviewElement.classList.add('rejected');
      reviewElement.classList.remove('accepted');
    }
    
    // Check if all reviews are complete
    this.checkReviewsComplete();
  }
  
  /**
   * Check if all reviews are complete and show the improve idea button if they are
   * No longer used as button appears after all reviews are generated, regardless of acceptance
   */
  checkReviewsComplete() {
    const allAspects = Object.keys(this.reviews);
    const handledAspects = [...this.acceptedReviews, ...this.rejectedReviews];
    
    // Add debug info
    console.log(`ReviewUI: Accepted aspects: ${this.acceptedReviews.join(', ')}`);
    console.log(`ReviewUI: Rejected aspects: ${this.rejectedReviews.join(', ')}`);
  }
  
  /**
   * Show the improve idea button only when all reviews are complete
   */
  showImproveIdeaButton() {
    // Only show the button if we have completed all expected reviews
    if (Object.keys(this.reviews).length < this.expectedAspects.length) {
      console.log('ReviewUI: Not all reviews completed yet');
      return;
    }

    // Check if button already exists
    if (document.getElementById('improve-idea-btn')) {
      return;
    }
    
    console.log('ReviewUI: All reviews completed, showing improve button');
    
    const chatArea = document.getElementById('chat-box');
    if (!chatArea) {
      console.error('ReviewUI: Chat area not found');
      return;
    }
    
    // Create a wrapper with system sender attribute
    const wrapper = document.createElement('div');
    wrapper.setAttribute('data-sender', 'system');
    wrapper.className = 'improve-idea-container';
    
    // Create completion message
    const completionMessage = document.createElement('div');
    completionMessage.className = 'review-completion-message';
    wrapper.appendChild(completionMessage);
    
    // Create the improve idea button
    const improveButton = document.createElement('button');
    improveButton.id = 'improve-idea-btn';
    improveButton.className = 'improve-idea-btn';
    improveButton.innerHTML = 'Improve Idea Based on Feedback';
    improveButton.onclick = () => this.improveIdea();
    wrapper.appendChild(improveButton);
    
    chatArea.appendChild(wrapper);
    chatArea.scrollTop = chatArea.scrollHeight;
  }
  
  /**
   * Get the reviews with the lowest scores if not enough have been explicitly accepted
   * @returns {Array} Array of aspect names with lowest scores
   */
  getReviewsWithLowestScores() {
    const reviewEntries = Object.entries(this.reviews);
    if (reviewEntries.length === 0) {
      return [];
    }
    
    // Sort reviews by score (ascending)
    const sortedReviews = reviewEntries.sort((a, b) => {
      const scoreA = a[1].score || 0;
      const scoreB = b[1].score || 0;
      return scoreA - scoreB;
    });
    
    // Get the necessary number of lowest-scoring aspects
    const neededCount = Math.max(0, this.minAcceptedReviews - this.acceptedReviews.length);
    const lowestScoringAspects = [];
    
    for (let i = 0; i < sortedReviews.length && lowestScoringAspects.length < neededCount; i++) {
      const [aspect] = sortedReviews[i];
      // Only add if not already accepted
      if (!this.acceptedReviews.includes(aspect)) {
        lowestScoringAspects.push(aspect);
      }
    }
    
    return lowestScoringAspects;
  }
  
  /**
   * Improve the idea based on accepted feedback
   */
  improveIdea() {
    console.log('ReviewUI: Improving idea based on feedback');
    
    // Disable the button to prevent multiple clicks
    const improveButton = document.getElementById('improve-idea-btn');
    if (improveButton) {
      improveButton.disabled = true;
      improveButton.textContent = 'Improving idea...';
    }
    
    // Clear highlights before starting the improvement process
    this.clearHighlight();
    
    // If we don't have enough accepted reviews, automatically add the lowest-scoring ones
    if (this.acceptedReviews.length < this.minAcceptedReviews) {
      const lowScoringAspects = this.getReviewsWithLowestScores();
      console.log(`ReviewUI: Adding ${lowScoringAspects.length} low-scoring aspects: ${lowScoringAspects.join(', ')}`);
      
      // Add these aspects to accepted reviews
      lowScoringAspects.forEach(aspect => {
        if (!this.acceptedReviews.includes(aspect)) {
          this.acceptedReviews.push(aspect);
          
          // Also update the UI to show these as accepted
          const reviewElement = document.getElementById(`review-box-${aspect}`);
          if (reviewElement) {
            reviewElement.classList.add('accepted');
            reviewElement.classList.remove('rejected');
          }
        }
      });
      
      // Add a message to indicate automatic selection
      const chatArea = document.getElementById('chat-box');
      if (chatArea && lowScoringAspects.length > 0) {
        const autoSelectMsg = document.createElement('div');
        autoSelectMsg.setAttribute('data-sender', 'system');
        autoSelectMsg.className = 'auto-select-message';
        autoSelectMsg.textContent = `Automatically selected ${lowScoringAspects.length} reviews with the lowest scores to get enough feedback.`;
        chatArea.appendChild(autoSelectMsg);
      }
    }
    
    // Collect accepted reviews
    const acceptedReviewData = this.acceptedReviews.map(aspect => {
      return {
        aspect: aspect,
        ...this.reviews[aspect]
      };
    });
    
    console.log(`ReviewUI: Using ${acceptedReviewData.length} reviews for improvement`);
    
    // Get the current idea text
    const ideaText = document.getElementById('main-idea').innerText;
    
    // Create a system message indicating the improvement process
    const chatArea = document.getElementById('chat-box');
    const processingMsg = document.createElement('div');
    processingMsg.setAttribute('data-sender', 'system');
    processingMsg.textContent = 'Improving your research idea based on accepted feedback...';
    chatArea.appendChild(processingMsg);
    
    // Call the API to improve the idea
    $.ajax({
      url: '/api/improve_idea',
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        idea: ideaText,
        accepted_reviews: acceptedReviewData
      }),
      success: (data) => {
        const responseTime = new Date().toISOString();
        console.log(`ReviewUI: AJAX response received at ${responseTime}`);
        console.log('ReviewUI: Response structure:', JSON.stringify(Object.keys(data), null, 2));
        
        if (improveButton) {
          improveButton.textContent = 'Idea Improved!';
          improveButton.disabled = true;
        }
        
        if (data.improved_idea) {
          console.log(`ReviewUI: Improved idea received:`, data.improved_idea);
          
          // FIX: Handle case where improved_idea is an array or object properly
          let improvedIdeaText = data.improved_idea;
          
          if (Array.isArray(data.improved_idea)) {
            console.log('ReviewUI: improved_idea is an array, processing content');
            
            // Take the first element of the array
            const firstElement = data.improved_idea[0];
            
            if (typeof firstElement === 'string') {
              // If it's a string (possibly JSON), try to parse it
              try {
                console.log('ReviewUI: Attempting to parse JSON content');
                console.log('ReviewUI: Raw JSON content:', firstElement);
                const jsonObj = JSON.parse(firstElement);
                console.log('ReviewUI: Successfully parsed JSON object', Object.keys(jsonObj));
                
                // Format it nicely with spacing for better readability
                improvedIdeaText = JSON.stringify(jsonObj, null, 2);
                console.log('ReviewUI: Formatted JSON for display');
              } catch (error) {
                console.error('ReviewUI: Error parsing JSON string, using raw content', error);
                improvedIdeaText = firstElement;
              }
            } else if (typeof firstElement === 'object' && firstElement !== null) {
              // If it's already an object, just stringify it nicely
              console.log('ReviewUI: First element is already an object', Object.keys(firstElement));
              improvedIdeaText = JSON.stringify(firstElement, null, 2);
              console.log('ReviewUI: Converted object to formatted JSON string');
            } else {
              // Fallback if it's neither string nor object
              console.log('ReviewUI: First element is neither string nor object, using raw array');
              improvedIdeaText = JSON.stringify(data.improved_idea, null, 2);
            }
          } else if (typeof data.improved_idea === 'object' && data.improved_idea !== null) {
            // Handle case where improved_idea is a direct object
            console.log('ReviewUI: improved_idea is an object, converting to string');
            improvedIdeaText = JSON.stringify(data.improved_idea, null, 2);
          }
          
          // Make sure improvedIdeaText is a string before using substring
          if (typeof improvedIdeaText !== 'string') {
            console.log('ReviewUI: improvedIdeaText is not a string, converting');
            improvedIdeaText = String(improvedIdeaText);
          }
          
          console.log(`ReviewUI: Processed idea length: ${improvedIdeaText.length} characters`);
          console.log(`ReviewUI: Processed idea first 100 chars: "${improvedIdeaText.substring(0, 100)}..."`);
          
          // Add a simple status message to chat - don't put the full idea in chat
          const statusMsg = document.createElement('div');
          statusMsg.setAttribute('data-sender', 'system');
          statusMsg.className = 'success-message';
          statusMsg.innerHTML = 'Your research idea has been improved based on feedback. See the Research Brief panel.';
          chatArea.appendChild(statusMsg);
          
          // Make sure we clear any existing highlights again before updating content
          this.clearHighlight();
          
          // Update only the main idea panel in the right sidebar
          const mainIdeaElement = document.getElementById('main-idea');
          console.log('ReviewUI: Main idea element found after response:', !!mainIdeaElement);
          
          if (mainIdeaElement) {
            // DEBUG: Before updating content
            console.log('ReviewUI: Main idea element before update:', {
              display: mainIdeaElement.style.display,
              visibility: window.getComputedStyle(mainIdeaElement).visibility,
              zIndex: window.getComputedStyle(mainIdeaElement).zIndex,
              contentLength: mainIdeaElement.innerHTML.length
            });
            
            // UPDATE THE GLOBAL VARIABLE - using processed improvedIdeaText
            console.log('ReviewUI: Setting window.main_idea to:', improvedIdeaText.substring(0, 50) + '...');
            window.main_idea = improvedIdeaText;
            
            // ADDING TIMESTAMP FOR VERIFICATION
            const timestamp = new Date().toISOString();
            
            // Prepare content for rendering
            let contentHtml = '';
            
            // Check if this looks like JSON content
            if (improvedIdeaText.trim().startsWith('{') && improvedIdeaText.includes('"title"')) {
              // This is JSON content, we'll format it nicely 
              console.log('ReviewUI: Detected JSON content, formatting nicely');
              try {
                // Parse it to ensure it's valid JSON
                const jsonObj = JSON.parse(improvedIdeaText);
                
                // Create a more readable HTML display with sections
                contentHtml = `<h2 class="section-header">${jsonObj.title || 'Research Idea'}</h2>`;
                
                // Define the correct order of sections
                const sectionOrder = ['title', 'proposed_method', 'experiment_plan'];
                
                // Add each section from the JSON in the specified order
                for (const key of sectionOrder) {
                  if (key !== 'title' && jsonObj[key]) { // Title already displayed
                    const sectionTitle = key.replace(/_/g, ' ')
                      .split(' ')
                      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                      .join(' ');
                    
                    // Parse the value using marked to render the markdown within the section
                    let renderedValue = jsonObj[key];
                    if (typeof marked !== 'undefined') {
                      try {
                        renderedValue = marked.parse(jsonObj[key]);
                        console.log(`ReviewUI: Markdown rendered for section ${key}`);
                      } catch (err) {
                        console.error(`ReviewUI: Error rendering markdown for section ${key}`, err);
                      }
                    }
                    
                    contentHtml += `
                      <h3 class="section-header">${sectionTitle}</h3>
                      <div class="json-section">${renderedValue}</div>
                    `;
                  }
                }
                
                // Add any remaining sections that weren't in the predefined order
                for (const [key, value] of Object.entries(jsonObj)) {
                  if (key !== 'title' && !sectionOrder.includes(key)) {
                    const sectionTitle = key.replace(/_/g, ' ')
                      .split(' ')
                      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                      .join(' ');
                    
                    // Parse the value using marked to render the markdown
                    let renderedValue = value;
                    if (typeof marked !== 'undefined') {
                      try {
                        renderedValue = marked.parse(value);
                        console.log(`ReviewUI: Markdown rendered for section ${key}`);
                      } catch (err) {
                        console.error(`ReviewUI: Error rendering markdown for section ${key}`, err);
                      }
                    }
                    
                    contentHtml += `
                      <h3 class="section-header">${sectionTitle}</h3>
                      <div class="json-section">${renderedValue}</div>
                    `;
                  }
                }
                
                // Set content directly
                mainIdeaElement.innerHTML = contentHtml;
                console.log('ReviewUI: Updated content with formatted JSON sections + markdown rendering');
                
                // Add custom CSS to improve the formatting of lists and sections
                const styleId = 'review-ui-custom-styles';
                let styleEl = document.getElementById(styleId);
                
                // Create style element if it doesn't exist yet
                if (!styleEl) {
                  styleEl = document.createElement('style');
                  styleEl.id = styleId;
                  document.head.appendChild(styleEl);
                }
                
                styleEl.textContent = `
                  #main-idea .json-section ul, 
                  #main-idea .json-section ol {
                    padding-left: 20px;
                    margin: 10px 0;
                  }
                  #main-idea .json-section li {
                    margin-bottom: 5px;
                  }
                  #main-idea .json-section p {
                    margin-bottom: 10px;
                  }
                  #main-idea .section-header {
                    margin-top: 20px;
                    margin-bottom: 10px;
                    border-bottom: 1px solid #eaeaea;
                    padding-bottom: 5px;
                  }
                  #main-idea h2.section-header {
                    margin-top: 0;
                  }
                `;
                
              } catch (error) {
                console.error('ReviewUI: Error formatting JSON content', error);
                // Fallback to using marked
                if (typeof marked !== 'undefined') {
                  try {
                    const parsedContent = marked.parse(improvedIdeaText);
                    mainIdeaElement.innerHTML = parsedContent;
                    console.log('ReviewUI: Fallback to marked parsing');
                  } catch (markError) {
                    mainIdeaElement.innerHTML = `<pre>${improvedIdeaText}</pre>`;
                    console.log('ReviewUI: Double fallback to pre tag');
                  }
                } else {
                  mainIdeaElement.innerHTML = `<pre>${improvedIdeaText}</pre>`;
                  console.log('ReviewUI: Fallback to pre tag');
                }
              }
            } else {
              // Not JSON or uncertain format, use marked if available
              if (typeof marked !== 'undefined') {
                console.log('ReviewUI: Using marked for non-JSON content');
                try {
                  const parsedContent = marked.parse(improvedIdeaText);
                  mainIdeaElement.innerHTML = parsedContent;
                  console.log('ReviewUI: Updated content with marked');
                } catch (error) {
                  console.error('ReviewUI: Error parsing with marked', error);
                  mainIdeaElement.innerHTML = `<pre>${improvedIdeaText}</pre>`;
                  console.log('ReviewUI: Fallback to pre tag');
                }
              } else {
                console.log('ReviewUI: Marked not available, using pre tag');
                mainIdeaElement.innerHTML = `<pre>${improvedIdeaText}</pre>`;
              }
            }
            
            // Make sure the main idea is visible
            mainIdeaElement.style.display = 'block';
            console.log('ReviewUI: Set mainIdeaElement display to block');
            
            // Also hide placeholder if it exists
            const briefPlaceholder = document.getElementById('brief-placeholder');
            if (briefPlaceholder) {
              briefPlaceholder.style.display = 'none';
              console.log('ReviewUI: Set briefPlaceholder display to none');
            }
            
            // Make sure highlights are cleared one more time after content is updated
            setTimeout(() => this.clearHighlight(), 100);

            this.acceptedReviews.forEach(aspect => {
              const reviewCard = document.getElementById(`review-box-${aspect}`);
              if (reviewCard) {
                reviewCard.classList.add('completed');
              }
            });
            
            // Refresh the tree visualization if in tree mode
            if (typeof loadTree === 'function') {
              console.log('ReviewUI: Calling loadTree function');
              loadTree();
            }
          }
        } else {
          const errorMsg = document.createElement('div');
          errorMsg.setAttribute('data-sender', 'system');
          errorMsg.className = 'error-message';
          errorMsg.textContent = 'Sorry, there was an error improving your idea.';
          chatArea.appendChild(errorMsg);
        }
        
        // Scroll to see the result
        chatArea.scrollTop = chatArea.scrollHeight;
      },
      error: (xhr, status, error) => {
        console.error('ReviewUI: Error improving idea', {status, error, response: xhr.responseText});
        
        if (improveButton) {
          improveButton.disabled = false;
          improveButton.textContent = 'Improve Idea Based on Feedback';
        }
        
        const errorMsg = document.createElement('div');
        errorMsg.setAttribute('data-sender', 'system');
        errorMsg.className = 'error-message';
        errorMsg.textContent = 'Sorry, there was an error improving your idea.';
        chatArea.appendChild(errorMsg);
      }
    });
  }
  
  /**
   * Clear highlighted text in the main idea panel
   */
  clearHighlight() {
    console.log('ReviewUI: Clearing all highlights from main idea');
    
    const mainIdea = document.getElementById('main-idea');
    if (!mainIdea) {
      console.error('ReviewUI: Main idea element not found');
      return;
    }
    
    try {
      // Method 1: Use DOM manipulation to carefully remove highlight spans while preserving content
      const highlightSpans = mainIdea.querySelectorAll('span.review-highlight');
      console.log(`ReviewUI: Found ${highlightSpans.length} highlights to remove`);
      
      if (highlightSpans.length > 0) {
        highlightSpans.forEach(span => {
          // Replace the span with its text content
          const textNode = document.createTextNode(span.textContent);
          span.parentNode.replaceChild(textNode, span);
        });
        
        console.log('ReviewUI: All highlights removed via DOM manipulation');
      }
    } catch (error) {
      console.error('ReviewUI: Error clearing highlights', error);
    }
  }
  
  /**
   * Highlight text for the given aspect using fuzzy matching
   * @param {string} aspect - The aspect to highlight text for
   */
  highlightText(aspect) {
    console.log(`ReviewUI: Highlighting text for ${aspect}`);
    
    // Check if this aspect is already highlighted
    const existingHighlight = document.querySelector(`span.review-highlight[data-aspect="${aspect}"]`);
    if (existingHighlight) {
      console.log(`ReviewUI: ${aspect} is already highlighted, skipping`);
      return;
    }
    
    const review = this.reviews[aspect];
    if (!review || !review.highlight || !review.highlight.text) {
      console.log('ReviewUI: No highlight text found in review data');
      return;
    }
    
    const mainIdea = document.getElementById('main-idea');
    if (!mainIdea) {
      console.error('ReviewUI: Main idea element not found');
      return;
    }

    const searchText = review.highlight.text;
    console.log(`ReviewUI: Highlighting text: "${searchText}"`);
    
    // Store the original content for potential restoration
    const originalContent = mainIdea.innerHTML;
    
    try {
      // First try exact match using DOM parsing to preserve HTML structure
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = originalContent;
      const textNodes = [];
      
      // Helper function to collect all text nodes
      function collectTextNodes(node) {
        if (node.nodeType === Node.TEXT_NODE) {
          textNodes.push(node);
        } else {
          for (const child of node.childNodes) {
            collectTextNodes(child);
          }
        }
      }
      
      // Collect all text nodes
      collectTextNodes(tempDiv);
      console.log(`ReviewUI: Found ${textNodes.length} text nodes to search`);
      
      // Try to find the text in any of the text nodes
      let foundMatch = false;
      
      for (const textNode of textNodes) {
        const nodeText = textNode.textContent;
        const index = nodeText.indexOf(searchText);
        
        if (index !== -1) {
          console.log('ReviewUI: Found exact match in text node');
          
          // Split the text node into three parts: before, highlight, after
          const beforeText = nodeText.substring(0, index);
          const highlightText = nodeText.substring(index, index + searchText.length);
          const afterText = nodeText.substring(index + searchText.length);
          
          // Create new nodes
          const beforeNode = document.createTextNode(beforeText);
          const highlightNode = document.createElement('span');
          highlightNode.className = 'review-highlight';
          highlightNode.setAttribute('data-aspect', aspect);
          highlightNode.textContent = highlightText;
          const afterNode = document.createTextNode(afterText);
          
          // Replace the original node with these three nodes
          const parent = textNode.parentNode;
          parent.insertBefore(beforeNode, textNode);
          parent.insertBefore(highlightNode, textNode);
          parent.insertBefore(afterNode, textNode);
          parent.removeChild(textNode);
          
          foundMatch = true;
          break;
        }
      }
      
      // If exact match found, update the main idea with our modified DOM
      if (foundMatch) {
        mainIdea.innerHTML = tempDiv.innerHTML;
        console.log('ReviewUI: Highlight applied with DOM manipulation');
        return;
      }
      
      console.log('ReviewUI: No exact match found, trying case-insensitive match');
      
      // If no exact match found, try case-insensitive match
      foundMatch = false;
      const lowerSearchText = searchText.toLowerCase();
      
      for (const textNode of textNodes) {
        const nodeText = textNode.textContent;
        const lowerNodeText = nodeText.toLowerCase();
        const index = lowerNodeText.indexOf(lowerSearchText);
        
        if (index !== -1) {
          console.log('ReviewUI: Found case-insensitive match in text node');
          
          // Use the actual text from the content with original casing
          const beforeText = nodeText.substring(0, index);
          const highlightText = nodeText.substring(index, index + searchText.length);
          const afterText = nodeText.substring(index + searchText.length);
          
          // Create new nodes
          const beforeNode = document.createTextNode(beforeText);
          const highlightNode = document.createElement('span');
          highlightNode.className = 'review-highlight';
          highlightNode.setAttribute('data-aspect', aspect);
          highlightNode.textContent = highlightText;
          const afterNode = document.createTextNode(afterText);
          
          // Replace the original node with these three nodes
          const parent = textNode.parentNode;
          parent.insertBefore(beforeNode, textNode);
          parent.insertBefore(highlightNode, textNode);
          parent.insertBefore(afterNode, textNode);
          parent.removeChild(textNode);
          
          foundMatch = true;
          break;
        }
      }
      
      // If case-insensitive match found, update the main idea
      if (foundMatch) {
        mainIdea.innerHTML = tempDiv.innerHTML;
        console.log('ReviewUI: Case-insensitive highlight applied with DOM manipulation');
        return;
      }
      
      // If still no match, try partial match by searching for parts of the text
      if (searchText.length > 15) {
        console.log('ReviewUI: Trying partial match with substring');
        const partialSearchText = searchText.substring(5, 15); // A portion of the middle
        console.log(`ReviewUI: Looking for partial text: "${partialSearchText}"`);
        
        for (const textNode of textNodes) {
          const nodeText = textNode.textContent;
          const index = nodeText.indexOf(partialSearchText);
          
          if (index !== -1) {
            console.log('ReviewUI: Found partial match in text node');
            
            // Try to expand to full sentence or reasonable context (20 chars before and after)
            const startIndex = Math.max(0, index - 20);
            const endIndex = Math.min(nodeText.length, index + partialSearchText.length + 20);
            
            const beforeText = nodeText.substring(0, startIndex);
            const highlightText = nodeText.substring(startIndex, endIndex);
            const afterText = nodeText.substring(endIndex);
            
            // Create new nodes
            const beforeNode = document.createTextNode(beforeText);
            const highlightNode = document.createElement('span');
            highlightNode.className = 'review-highlight';
            highlightNode.setAttribute('data-aspect', aspect);
            highlightNode.textContent = highlightText;
            const afterNode = document.createTextNode(afterText);
            
            // Replace the original node with these three nodes
            const parent = textNode.parentNode;
            parent.insertBefore(beforeNode, textNode);
            parent.insertBefore(highlightNode, textNode);
            parent.insertBefore(afterNode, textNode);
            parent.removeChild(textNode);
            
            foundMatch = true;
            break;
          }
        }
        
        // If partial match found, update the main idea
        if (foundMatch) {
          mainIdea.innerHTML = tempDiv.innerHTML;
          console.log('ReviewUI: Partial highlight applied with DOM manipulation');
          return;
        }
      }
      
      // Last resort - use the simplified approach with innerHTML manipulation
      // but try to minimize the risk of breaking formatting
      console.log('ReviewUI: No DOM match found, using fallback approach');
      
      // Get the raw text content (without HTML)
      const rawTextContent = mainIdea.textContent;
      
      // Try to find an exact match in the raw text
      const rawIndex = rawTextContent.indexOf(searchText);
      if (rawIndex !== -1) {
        // Now we know the text exists in the raw content
        // Let's try a more careful approach with regex to avoid breaking HTML
        
        // Escape special regex characters in the search text
        const escapedSearchText = searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        
        // Create a regex that allows HTML tags within the search text
        // This is a simplification - won't work for all cases but is safer
        const regex = new RegExp(`(${escapedSearchText})`, 'g');
        
        // Replace the first occurrence with a highlighted span
        const newContent = originalContent.replace(regex, 
          `<span class="review-highlight" data-aspect="${aspect}">$1</span>`);
        
        if (newContent !== originalContent) {
          mainIdea.innerHTML = newContent;
          console.log('ReviewUI: Applied highlight with regex replacement');
          return;
        }
      }
      
      // If all else fails, just log the failure
      console.log('ReviewUI: Could not find suitable match for highlighting');
      
    } catch (error) {
      // If any error occurs, restore the original content to prevent breaking the UI
      console.error('ReviewUI: Error during highlighting', error);
      mainIdea.innerHTML = originalContent;
    }
  }
  
  /**
   * Show loading state for an aspect
   * @param {string} aspect - The aspect being loaded
   */
  showLoading(aspect) {
    console.log(`ReviewUI: Showing loading state for ${aspect}`);
    
    // Create a loading message in the chat
    const chatArea = document.getElementById('chat-box');
    if (chatArea) {
      const loadingMsg = document.createElement('div');
      loadingMsg.setAttribute('data-sender', 'system');
      loadingMsg.id = `loading-${aspect}`;
      loadingMsg.className = 'review-loading';
      loadingMsg.textContent = `Analyzing ${aspect}...`;
      
      chatArea.appendChild(loadingMsg);
      chatArea.scrollTop = chatArea.scrollHeight;
    }
  }
  
  /**
   * Hide loading state
   */
  hideLoading() {
    console.log('ReviewUI: Hiding loading states');
    const loadingElements = document.querySelectorAll('.review-loading');
    console.log(`ReviewUI: Found ${loadingElements.length} loading elements to remove`);
    loadingElements.forEach(el => el.remove());
  }
  
  /**
   * Reset all review state
   */
  reset() {
    console.log('ReviewUI: Resetting review state');
    
    // Reset data states
    this.reviews = {};
    this.acceptedReviews = [];
    this.rejectedReviews = [];
    this.activeAspect = null;
    
    // Clear any UI elements that might remain
    this.clearHighlight();
    
    // Remove any existing improve button
    const existingButton = document.getElementById('improve-idea-btn');
    if (existingButton) {
      const container = existingButton.parentElement;
      if (container) {
        container.remove();
      } else {
        existingButton.remove();
      }
    }
    
    // Remove any existing review cards
    const reviewCards = document.querySelectorAll('[id^="review-box-"]');
    reviewCards.forEach(card => {
      const container = card.parentElement;
      if (container && container.classList.contains('review-message-container')) {
        container.remove();
      }
    });
    
    console.log('ReviewUI: Reset complete');
  }
}

// Create and export a singleton instance
const reviewUI = new ReviewUI();
console.log('ReviewUI: Created singleton instance');
