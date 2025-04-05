/**
 * Debug tools for the IRIS review functionality
 * This file adds debugging utilities to test the review UI without
 * having to trigger the actual review process
 */

// Create debug namespace if it doesn't exist
window.IRISDebug = window.IRISDebug || {};

// Debug functions for review system
IRISDebug.Reviews = {
  // Add example reviews to test the UI
  addExamples: function() {
    console.log("Debug: Adding example review boxes");
    
    // Make sure ReviewUI is initialized
    if (!reviewUI.initialized) {
      reviewUI.init('review-container');
    }
    
    // Make sure review container is visible
    const container = document.getElementById('review-container');
    if (container) {
      container.style.display = 'block';
      console.log("Debug: Set review container to visible");
    }
    
    // Example review data
    const exampleData = {
      novelty: {
        aspect: "novelty",
        score: 7,
        summary: "The idea introduces some novel concepts but could be more original.",
        highlight: {
          text: "machine learning for climate prediction",
          category: "Moderately Novel Concept",
          review: "This approach has been explored before but your angle seems somewhat fresh."
        }
      },
      feasibility: {
        aspect: "feasibility",
        score: 8,
        summary: "The approach seems reasonably achievable with current technology.",
        highlight: {
          text: "using existing satellite data",
          category: "Resource Availability",
          review: "Good use of available resources which strengthens feasibility."
        }
      },
      clarity: {
        aspect: "clarity",
        score: 6,
        summary: "The proposal could be clearer in some areas.",
        highlight: {
          text: "implement a neural network architecture",
          category: "Vague Implementation",
          review: "This statement needs more specific details on the architecture type and design."
        }
      },
      impact: {
        aspect: "impact",
        score: 9,
        summary: "The potential impact of this research is significant.",
        highlight: {
          text: "could benefit millions of people in developing regions",
          category: "High Social Impact",
          review: "The social impact claim is substantial and well-justified."
        }
      },
      methodology: {
        aspect: "methodology",
        score: 5,
        summary: "The methodology requires more detailed planning.",
        highlight: {
          text: "data collection from multiple sources",
          category: "Methodology Gap",
          review: "The data collection process needs more specific details on sources and integration methods."
        }
      }
    };
    
    // Add each example review
    Object.values(exampleData).forEach((data, i) => {
      reviewUI.addReview(data.aspect, data, i === 0);
      console.log(`Debug: Added example review for ${data.aspect}`);
    });
    
    console.log("Debug: All example reviews added");
    
    // Add a message to the chat to indicate this is a debug action
    const chatArea = $("#chat-box");
    if (chatArea.length) {
      const debugMessage = $('<div></div>')
        .attr('data-sender', 'system')
        .html('<strong>DEBUG:</strong> Added example review boxes for testing')
        .hide();
      
      chatArea.append(debugMessage);
      debugMessage.slideDown();
      chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
    }
    
    return "Debug reviews added successfully";
  },
  
  // Clear all review boxes
  clear: function() {
    console.log("Debug: Clearing all review boxes");
    
    const boxesContainer = document.querySelector('.review-boxes');
    if (boxesContainer) {
      boxesContainer.innerHTML = '';
      console.log("Debug: Cleared review boxes");
    } else {
      console.log("Debug: Review boxes container not found");
    }
    
    return "Review boxes cleared";
  },
  
  // Toggle the visibility of the review container
  toggleContainer: function() {
    const container = document.getElementById('review-container');
    if (container) {
      const currentDisplay = window.getComputedStyle(container).display;
      container.style.display = currentDisplay === 'none' ? 'block' : 'none';
      console.log(`Debug: Set review container display to ${container.style.display}`);
      return `Review container is now ${container.style.display === 'none' ? 'hidden' : 'visible'}`;
    } else {
      console.log("Debug: Review container not found");
      return "Review container not found";
    }
  },
  
  // Check the state of the review system
  status: function() {
    console.log("Debug: Checking review system status");
    
    const status = {
      reviewUIInitialized: typeof reviewUI !== 'undefined' && reviewUI.initialized,
      containerExists: document.getElementById('review-container') !== null,
      containerVisible: document.getElementById('review-container') ? 
                        window.getComputedStyle(document.getElementById('review-container')).display !== 'none' : 
                        false,
      reviewBoxesCount: document.querySelectorAll('.review-box').length,
      activeReviews: reviewUI && reviewUI.reviews ? Object.keys(reviewUI.reviews) : [],
      activeAspect: reviewUI ? reviewUI.activeAspect : null
    };
    
    console.log("Debug: Review system status", status);
    return status;
  }
};

// Add console message about debug tools
console.log('Debug tools loaded. Access via IRISDebug.Reviews in the console.');
console.log('Available commands:');
console.log('- IRISDebug.Reviews.addExamples() - Add example reviews');
console.log('- IRISDebug.Reviews.clear() - Clear all reviews');
console.log('- IRISDebug.Reviews.toggleContainer() - Toggle container visibility');
console.log('- IRISDebug.Reviews.status() - Check review system status');