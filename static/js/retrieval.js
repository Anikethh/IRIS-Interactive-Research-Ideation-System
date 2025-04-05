// Add these functions at the top of the file to handle the custom modal

function showQueryEditModal(currentQuery, callback) {
    // Set the current query in the textarea
    const textarea = document.getElementById('edit-query-textarea');
    textarea.value = currentQuery;
    
    // Store the callback for later use
    window.currentQueryEditCallback = callback;
    
    // Show the modal and overlay
    document.getElementById('edit-query-modal').style.display = 'block';
    document.getElementById('modal-overlay').style.display = 'block';
}

function closeQueryModal() {
    document.getElementById('edit-query-modal').style.display = 'none';
    document.getElementById('modal-overlay').style.display = 'none';
}

function saveQueryEdit() {
    const editedQuery = document.getElementById('edit-query-textarea').value;
    closeQueryModal();
    
    // Execute the callback with the edited query
    if (window.currentQueryEditCallback) {
        window.currentQueryEditCallback(editedQuery);
        window.currentQueryEditCallback = null;
    }
}

// Retrieval functionality for IRIS
const retrieval = {
    // Store the current query and results
    currentQuery: null,
    currentResults: null,
    
    // Generate a query based on the current research idea
    generateQuery: async function() {
        const ideaText = $("#main-idea").text();
        if (!ideaText) {
            console.error("No research idea available for query generation");
            return null;
        }
        
        try {
            // Show query generation in progress
            this.showGeneratingQueryState();
            
            const response = await $.ajax({
                url: "/api/generate_query",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify({ idea: ideaText })
            });
            
            if (response && response.query) {
                this.currentQuery = response.query;
                
                // Show query confirmation UI
                this.showQueryConfirmationState(response.query);
                
                return response.query;
            } else {
                console.error("Failed to generate query:", response);
                this.showErrorState("Failed to generate a search query");
                return null;
            }
        } catch (error) {
            console.error("Error generating query:", error);
            this.showErrorState("Error generating search query");
            return null;
        }
    },
    
    // Retrieve knowledge based on the generated query
    retrieveKnowledge: async function(query) {
        // Use the provided query or generate a new one
        const queryToUse = query || this.currentQuery;
        
        if (!queryToUse) {
            const generatedQuery = await this.generateQuery();
            if (!generatedQuery) {
                return false;
            }
            // Don't proceed automatically - let user confirm query first
            return true;
        }
        
        try {
            // Show loading state
            this.showLoadingState();
            
            // Make the API call
            const response = await $.ajax({
                url: "/api/retrieve_knowledge",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify({ query: queryToUse })
            });
            
            // Store and display results
            if (response && response.sections) {
                this.currentResults = response;
                this.displayResults(response);
                return true;
            } else {
                console.error("Failed to retrieve knowledge:", response);
                this.showErrorState("No results found");
                return false;
            }
        } catch (error) {
            console.error("Error retrieving knowledge:", error);
            this.showErrorState("Error retrieving knowledge");
            return false;
        }
    },
    
    // Submit a direct search query from the search input field
    submitSearch: function() {
        // Get the search input value
        const searchInput = document.querySelector('.sidebar-search input');
        const query = searchInput ? searchInput.value.trim() : '';
        
        if (query) {
            // Store the query and start retrieval
            this.currentQuery = query;
            this.retrieveKnowledge(query);
            
            // Clear the search input
            searchInput.value = '';
        }
    },
    
    // Show generating query state in the center chat area
    showGeneratingQueryState: function() {
        // Add message to chat box
        $("#chat-box").append(`
            <div class="message-container" data-sender="system">
                <div class="loading-state">
                    <div class="spinner"></div>
                    <div class="loading-text">Generating search query based on research idea...</div>
                </div>
            </div>
        `);
        
        // Scroll to bottom of chat
        $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
    },
    
    // Show query confirmation UI in the center chat area
    showQueryConfirmationState: function(query) {
        // Remove loading message if exists
        $("#chat-box .message-container:last-child .loading-state").remove();
        
        // Add query confirmation UI to chat
        $("#chat-box").append(`
            <div class="message-container" data-sender="system">
                <div class="query-confirmation">
                    <div class="query-prompt">Generated search query:</div>
                    <div class="query-text">${query}</div>
                    <div class="query-actions">
                        <button class="confirm-query-btn">Proceed with this query</button>
                        <button class="edit-query-btn">Edit query</button>
                    </div>
                </div>
            </div>
        `);
        
        // Scroll to bottom of chat
        $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
        
        // Add event handlers
        $(".confirm-query-btn").click(() => {
            this.retrieveKnowledge(this.currentQuery);
        });
        
        $(".edit-query-btn").click(() => {
            const currentQuery = this.currentQuery || "";
            showQueryEditModal(currentQuery, (editedQuery) => {
                if (editedQuery && editedQuery.trim() !== "") {
                    this.currentQuery = editedQuery.trim();
                    this.showQueryConfirmationState(this.currentQuery);
                }
            });
        });
    },
    
    // Show loading state in the center chat area
    showLoadingState: function() {
        // Remove query confirmation if exists
        $("#chat-box .message-container:last-child .query-confirmation").remove();
        
        // Add loading message
        $("#chat-box").append(`
            <div class="message-container" data-sender="system">
                <div class="loading-state">
                    <div class="spinner"></div>
                    <div class="loading-text">Searching for relevant papers...</div>
                </div>
            </div>
        `);
        
        // Scroll to bottom of chat
        $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
    },
    
    // Show error state in the center chat area
    showErrorState: function(message) {
        // Remove loading message if exists
        $("#chat-box .message-container:last-child .loading-state").remove();
        
        // Add error message
        $("#chat-box").append(`
            <div class="message-container" data-sender="system">
                <div class="error-state">
                    <div class="error-icon">❌</div>
                    <div class="error-text">${message}</div>
                    <button class="retry-button">Try Again</button>
                </div>
            </div>
        `);
        
        // Scroll to bottom of chat
        $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
        
        // Add retry button handler
        $(".retry-button").click(() => this.generateQuery());
    },
    
    // Display retrieval results in the left sidebar (keeping this functionality)
    displayResults: function(results) {
        // Display in left sidebar
        $("#qa-placeholder").hide();
        $("#qa-content").empty().show();
        
        // Add query at the top with minimal styling
        $("#qa-content").append(`
            <div class="query-header">
                <div class="query-title">Query:</div>
                <div class="query-text">${results.query}</div>
                <button class="edit-query-btn small">Edit</button>
            </div>
        `);
        
        // Add event handler for edit button
        $("#qa-content").find(".edit-query-btn").click(() => {
            const currentQuery = this.currentQuery || "";
            showQueryEditModal(currentQuery, (editedQuery) => {
                if (editedQuery && editedQuery.trim() !== "") {
                    this.currentQuery = editedQuery.trim();
                    this.retrieveKnowledge(this.currentQuery);
                }
            });
        });
        
        // Add each section with minimalist design (thin lines instead of boxes)
        results.sections.forEach(section => {
            const sectionElement = $(`
                <div class="qa-item">
                    <div class="question">${section.title}</div>
                    <div class="answer">
                        <div class="section-summary">${section.summary}</div>
                        <div class="section-content">${marked.parse(section.content)}</div>
                    </div>
                </div>
            `);
            
            // Add citations if available - with dropdown functionality
            if (section.citations && section.citations.length > 0) {
                const citationsDropdown = $(`
                    <div class="citations-container">
                        <h4 class="citations-toggle">References (${section.citations.length})<span class="toggle-icon">▼</span></h4>
                        <div class="citations-list" style="display: none;"></div>
                    </div>
                `);
                
                const citationsList = citationsDropdown.find('.citations-list');
                
                section.citations.forEach(citation => {
                    // Format author citation prefix
                    let authorCitation = '';
                    
                    if (citation.paper && citation.paper.authors && citation.paper.authors.length > 0) {
                        if (citation.paper.authors.length === 1) {
                            authorCitation = `${citation.paper.authors[0].name.split(' ').pop()}`;
                        } else {
                            authorCitation = `${citation.paper.authors[0].name.split(' ').pop()} et al.`;
                        }
                    } else if (citation.authors && citation.authors.length > 0) {
                        if (citation.authors.length === 1) {
                            authorCitation = `${citation.authors[0].split(' ').pop()}`;
                        } else {
                            authorCitation = `${citation.authors[0].split(' ').pop()} et al.`;
                        }
                    }
                    
                    // Add year if available
                    if (citation.year) {
                        authorCitation += ` (${citation.year})`;
                    }
                    
                    const citationElement = $(`
                        <div class="citation-item">
                            <div class="citation-link">
                                <span class="citation-prefix">${authorCitation}</span>
                                <a href="${citation.url}" target="_blank">${citation.title}</a>
                            </div>
                        </div>
                    `);
                    
                    citationsList.append(citationElement);
                });
                
                // Add click handler for dropdown toggle
                citationsDropdown.find('.citations-toggle').click(function() {
                    $(this).siblings('.citations-list').slideToggle(200);
                    // Toggle the arrow icon
                    const toggleIcon = $(this).find('.toggle-icon');
                    if (toggleIcon.text() === '▼') {
                        toggleIcon.text('▲');
                    } else {
                        toggleIcon.text('▼');
                    }
                });
                
                sectionElement.find('.answer').append(citationsDropdown);
            }
            
            $("#qa-content").append(sectionElement);
        });
        
        // Now also show a summary of results in chat area
        this.displayResultsInChat(results);
    },
    
    // Display a summary of results in the chat area
    displayResultsInChat: function(results) {
        // Remove loading message if exists
        $("#chat-box .message-container:last-child .loading-state").remove();
        
        // Create a summary of the results
        let summaryContent = `<div class="retrieval-results">
            <h3>Knowledge Retrieved</h3>
            <p>Retrieved information about <strong>${results.query}</strong></p>
            <ul class="retrieval-sections">`;
            
        results.sections.forEach(section => {
            summaryContent += `<li>${section.title}</li>`;
        });
        
        summaryContent += `</ul>
            <p>The complete results are available in the left panel.</p>
            <div class="improve-button-container">
                <button class="improve-with-knowledge-btn">Improve Idea with Retrieved Knowledge</button>
            </div>
        </div>`;
        
        // Add to chat
        $("#chat-box").append(`
            <div class="message-container" data-sender="system">
                ${summaryContent}
            </div>
        `);
        
        // Scroll to bottom of chat
        $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
        
        // Add handler for improve button
        $(".improve-with-knowledge-btn").click(() => {
            this.improveIdeaWithKnowledge();
        });
    },
    
    // Function to improve idea with retrieved knowledge
    improveIdeaWithKnowledge: function() {
        // Get the current idea text
        const ideaText = document.getElementById('main-idea').innerText;
        
        // Add message to chat about improvement process
        $("#chat-box").append(`
            <div class="message-container" data-sender="system">
                <div class="loading-state">
                    <div class="spinner"></div>
                    <div class="loading-text">Improving research idea with retrieved knowledge...</div>
                </div>
            </div>
        `);
        
        // Scroll to bottom of chat
        $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
        
        // Call the API to improve the idea with knowledge
        $.ajax({
            url: "/api/improve_idea_with_knowledge",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                idea: ideaText
            }),
            success: (data) => {
                console.log('Retrieval: Idea improvement response received', data);
                
                // Remove loading state
                $("#chat-box .message-container:last-child .loading-state").remove();
                
                if (data.improved_idea) {
                    // Add a simple status message to chat
                    const statusMsg = document.createElement('div');
                    statusMsg.setAttribute('data-sender', 'system');
                    statusMsg.className = 'success-message';
                    statusMsg.innerHTML = 'Your research idea has been improved based on the retrieved knowledge. See the Research Brief panel.';
                    $("#chat-box").append(statusMsg);
                    
                    // Update only the main idea panel in the right sidebar
                    const mainIdeaElement = document.getElementById('main-idea');
                    if (mainIdeaElement) {
                        // Use marked for proper markdown rendering
                        if (typeof marked !== 'undefined') {
                            mainIdeaElement.innerHTML = marked.parse(data.improved_idea);
                        } else {
                            // Fallback if marked is not available
                            mainIdeaElement.innerHTML = data.improved_idea;
                        }
                        
                        // Make sure the main idea is visible
                        mainIdeaElement.style.display = 'block';
                        // Also hide placeholder if it exists
                        const briefPlaceholder = document.getElementById('brief-placeholder');
                        if (briefPlaceholder) {
                            briefPlaceholder.style.display = 'none';
                        }
                        
                        // Refresh the tree visualization if in tree mode
                        if (typeof loadTree === 'function') {
                            loadTree();
                        }
                    }
                } else {
                    const errorMsg = document.createElement('div');
                    errorMsg.setAttribute('data-sender', 'system');
                    errorMsg.className = 'error-message';
                    errorMsg.textContent = 'Sorry, there was an error improving your idea with the retrieved knowledge.';
                    $("#chat-box").append(errorMsg);
                }
                
                // Scroll to see the result
                $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
            },
            error: (xhr, status, error) => {
                console.error('Retrieval: Error improving idea', {status, error, response: xhr.responseText});
                
                // Remove loading state
                $("#chat-box .message-container:last-child .loading-state").remove();
                
                const errorMsg = document.createElement('div');
                errorMsg.setAttribute('data-sender', 'system');
                errorMsg.className = 'error-message';
                errorMsg.textContent = 'Sorry, there was an error improving your idea with the retrieved knowledge.';
                $("#chat-box").append(errorMsg);
                
                // Scroll to see the error
                $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
            }
        });
    }
};

// Add click handler for the Retrieve Knowledge button
$(document).ready(function() {
    // Handler for Retrieve Knowledge button
    $(".retrieve-knowledge").on("click", function() {
        retrieval.generateQuery();
    });
    
    // Handler for the search input in the sidebar
    $(".sidebar-search input").on("keypress", function(e) {
        if(e.which === 13) { // Enter key
            e.preventDefault();
            retrieval.submitSearch();
        }
    });
    
    // Handler for the search button in the sidebar
    $(".sidebar-search button").on("click", function() {
        retrieval.submitSearch();
    });
});