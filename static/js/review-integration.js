/**
 * Integration code to connect the review UI with the existing app
 */
$(document).ready(function() {
  console.log('Review Integration: Initializing...');
  
  // Make sure the global state object exists
  if (typeof window.state === 'undefined') {
    window.state = {
      // New taxonomy of review aspects
      aspectsToReview: [
        "lack_of_novelty",
        "assumptions", 
        "vagueness",
        "feasibility_and_practicality",
        "overgeneralization",
        "overstatement",
        "evaluation_and_validation_issues",
        "justification_for_methods",
        "reproducibility",
        "contradictory_statements",
        "impact",
        "alignment",
        "ethical_and_social_considerations",
        "robustness"
      ],
      currentReviewAspectIndex: 0,
      acceptedReviews: [],
      reviewInProgress: false
    };
    console.log('Review Integration: Created global state object');
  }
  
  // Initialize the review UI
  reviewUI.init();
  console.log('Review Integration: UI initialized');
  
  // Add click handler for Generate Review button
  $(".generate-review").off('click').on('click', function() {
    console.log("Review Integration: Generate Review button clicked");
    triggerGenerateReview();
  });

  // Add helper to programmatically trigger review generation
  function triggerGenerateReview() {
    // Reset review state
    state.currentReviewAspectIndex = 0;
    state.acceptedReviews = [];
    state.reviewInProgress = true;
    reviewUI.reset();
    
    // Add a message to indicate the review is starting
    const chatArea = $("#chat-box");
    const reviewStartMessage = $('<div></div>')
      .attr('data-sender', 'system')
      .html('<strong>Starting Review Process</strong><p>Your research idea will be evaluated on multiple aspects including novelty, feasibility, clarity, and potential impact.</p>')
      .hide();
    
    chatArea.append(reviewStartMessage);
    reviewStartMessage.slideDown();
    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

    // Start the review process
    requestAspectReview(0);
  }

  // Export the trigger function for automated use
  window.triggerGenerateReview = triggerGenerateReview;

  // Override the original requestAspectReview function
  window.requestAspectReview = function(aspectIndex) {
    console.log(`Review Integration: Requesting review for aspect index ${aspectIndex}`);
    
    if (aspectIndex >= state.aspectsToReview.length) {
      console.log('Review Integration: Review process complete');
      const chatArea = $("#chat-box");
      const completionMessage = $('<div></div>')
        .attr('data-sender', 'system')
        .html('<strong>Review Process Complete</strong><p>Please accept or reject each review suggestion. Once you\'ve reviewed all suggestions, you can improve your research idea based on the accepted feedback.</p>')
        .hide();
      
      chatArea.append(completionMessage);
      completionMessage.slideDown();
      chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

      // Show the improve idea button
      reviewUI.showImproveIdeaButton();

      state.reviewInProgress = false;
      return;
    }

    const currentAspect = state.aspectsToReview[aspectIndex];
    console.log(`Review Integration: Processing aspect: ${currentAspect}`);
    
    // Show loading indicator in the chat
    reviewUI.showLoading(currentAspect);
    
    // Get the current research idea text
    const ideaText = $("#main-idea").text();
    
    $.ajax({
      url: '/api/review_aspect',
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        idea: ideaText,
        aspect: currentAspect,
        aspect_index: aspectIndex
      }),
      success: function(data) {
        console.log("Review Integration: Review data received", data);
        
        // Hide any loading indicators
        reviewUI.hideLoading();
        
        if (data.review_data) {
          // Add the review to the UI
          reviewUI.addReview(currentAspect, data.review_data);
          
          // Continue with next aspect after a short delay
          setTimeout(() => {
            state.currentReviewAspectIndex++;
            requestAspectReview(state.currentReviewAspectIndex);
          }, 1000);
        } else {
          console.error("Review Integration: No review data received");
          
          // Add error message to chat
          const errorMsg = $('<div></div>')
            .attr('data-sender', 'system')
            .text(`Failed to analyze ${currentAspect}. Moving to next aspect...`)
            .hide();
          
          chatArea.append(errorMsg);
          errorMsg.slideDown();
          chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
          
          // Continue to next aspect
          setTimeout(() => {
            state.currentReviewAspectIndex++;
            requestAspectReview(state.currentReviewAspectIndex);
          }, 500);
        }
      },
      error: function(xhr, status, error) {
        console.error('Review Integration: AJAX error', { status, error, response: xhr.responseText });
        reviewUI.hideLoading();
        
        // Add error message to chat
        const chatArea = $("#chat-box");
        const errorMsg = $('<div></div>')
          .attr('data-sender', 'system')
          .text(`Error analyzing ${currentAspect}: ${status}. Moving to next aspect...`)
          .hide();
        
        chatArea.append(errorMsg);
        errorMsg.slideDown();
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
        
        // Continue with next aspect despite error
        setTimeout(() => {
          state.currentReviewAspectIndex++;
          requestAspectReview(state.currentReviewAspectIndex);
        }, 500);
      }
    });
  };

  // Remove mock API implementation - we'll always use the real endpoint
  
  // Export functions for global use
  window.addHighlightClickHandlers = addHighlightClickHandlers;
  window.acceptReview = acceptReview;
  window.rejectReview = rejectReview;
  window.integrateReviewWithMCTS = integrateReviewWithMCTS;

});

// Review Integration Module with MCTS Support

// Add handlers for review highlight clicks and actions
function addHighlightClickHandlers() {
    $('.review-highlight').click(function(e) {
        e.preventDefault();
        
        const aspect = $(this).data('aspect');
        const category = $(this).data('category');
        const review = $(this).data('review');
        
        // Show review card in chat with MCTS tracking
        showReviewInChat(category, review, aspect, this);
    });
}

// Enhanced review actions with MCTS state tracking
function acceptReview(aspect, category, review, highlightElement) {
    // Track this review in MCTS state
    const reviewData = {
        aspect: aspect,
        category: category,
        review: review,
        accepted: true,
        timestamp: Date.now()
    };
    
    // Add to global state for MCTS
    mctsAuto.trackReviewAction(reviewData);
    
    // Update highlight styling
    if (highlightElement) {
        $(highlightElement).addClass('accepted');
    }
}

function rejectReview(highlightElement) {
    if (highlightElement) {
        $(highlightElement).addClass('rejected');
        
        // Track rejection in MCTS state
        const aspect = $(highlightElement).data('aspect');
        const category = $(highlightElement).data('category');
        const review = $(highlightElement).data('review');
        
        mctsAuto.trackReviewAction({
            aspect: aspect,
            category: category,
            review: review,
            accepted: false,
            timestamp: Date.now()
        });
    }
}

// Integrate reviews with MCTS exploration
function integrateReviewWithMCTS(reviewData) {
    // Add review data to current MCTS node
    mctsAuto.addReviewToNode(reviewData);
    
    // Update tree visualization if visible
    if (treeMode) {
        updateTreeVisualization(mctsAuto.getCurrentTreeData());
    }
}

// Export functions for global use
window.addHighlightClickHandlers = addHighlightClickHandlers;
window.acceptReview = acceptReview;
window.rejectReview = rejectReview;
window.integrateReviewWithMCTS = integrateReviewWithMCTS;
