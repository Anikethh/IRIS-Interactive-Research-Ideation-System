// Initialize state object
const state = {
    currentReviewAspectIndex: 0,
    aspectsToReview: ["lack_of_novelty", "assumptions", "vagueness", "feasibility_and_practicality", "overgeneralization", "overstatement", "evaluation_and_validation_issues", "justification_for_methods", "reproducibility", "contradictory_statements", "impact", "alignment", "ethical_and_social_considerations", "robustness"],
    acceptedReviews: [],
    reviewInProgress: false
};

const MCTS_CONFIG = {
    maxIterations: 5,
    explorationDelay: 3000,
    explorationConstant: 1.414,
    discountFactor: 0.95
};

// Add iteration tracking variable
let mctsIterationCount = 0;

// Initialize highlight state and tree variables
const highlightState = {
    rawIdea: "",
    highlights: [],
    lastContent: ""
};

let treeMode = false;
let treeData = null;
let current_root = null; // Initialize current_root

// Define main_idea as a global variable to store the current idea
let main_idea = "";

// Add this near the top of the file to ensure our function is available globally
let toggleFromAutoGenerate; 

$(document).ready(function () {
    loadKnowledge();
    loadChat();
    loadIdea(true); // Initial load, don't overwrite highlights

    // REMOVE the polling - this is what's causing highlights to disappear
    setInterval(loadIdea, 5000); 
    
    // Add CSS for score display
    addScoreDisplayStyles();
    
    // Check if the MCTS auto module has a toggleAutoGenerate function and use it
    if (typeof window.toggleAutoGenerate === 'function') {
        // Store a reference to the MCTS auto implementation
        toggleFromAutoGenerate = window.toggleAutoGenerate;
    }
});

// Configure marked for safe rendering
marked.setOptions({
    sanitize: true,
    breaks: true
});

function formatMessage(content) {
    try {
        // First ensure our styling for section headers is in place
        ensureSectionHeaderStyles();
        
        // Parse markdown content using marked
        let formattedContent = marked.parse(content);
        
        // Add section-header class to all h2 and h3 elements for consistent styling
        formattedContent = formattedContent
            .replace(/<h2([^>]*)>/g, '<h2$1 class="section-header">')
            .replace(/<h3([^>]*)>/g, '<h3$1 class="section-header">');
        
        return formattedContent;
    } catch (e) {
        console.error('Markdown parsing error:', e);
        return content;
    }
}

// Helper function to ensure consistent section header styling across the application
function ensureSectionHeaderStyles() {
    const styleId = 'section-header-styles';
    
    // Create style element if it doesn't exist yet
    if (!document.getElementById(styleId)) {
        const styleEl = document.createElement('style');
        styleEl.id = styleId;
        styleEl.textContent = `
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
        document.head.appendChild(styleEl);
    }
}

// New function to parse and format JSON structured ideas with fallback
function parseAndFormatStructuredIdea(ideaContent) {
    // Early exit for non-JSON content
    if (!ideaContent || (!ideaContent.includes('{') && !ideaContent.includes('}'))) {
        return ideaContent;
    }
    
    // Try direct JSON parsing first
    try {
        const jsonPattern = /({[\s\S]*})/g;
        const match = jsonPattern.exec(ideaContent);
        
        if (match && match[1]) {
            const jsonStr = match[1].trim();
            console.log("Found possible JSON:", jsonStr.substring(0, 100) + "...");
            
            const ideaJson = JSON.parse(jsonStr);
            
            if (ideaJson.title) {
                console.log("Successfully parsed structured idea JSON");
                
                let formattedContent = `# ${ideaJson.title}\n\n`;
                
                if (ideaJson.proposed_method) {
                    formattedContent += `## Proposed Method\n\n${ideaJson.proposed_method}\n\n***\n\n`;
                }
                
                if (ideaJson.experiment_plan) {
                    formattedContent += `## Experiment Plan\n\n${ideaJson.experiment_plan}\n\n***\n\n`;
                }
                
                if (ideaJson.test_case_examples) {
                    formattedContent += `## Test Case Examples\n\n${ideaJson.test_case_examples}\n\n`;
                }
                
                if (ideaJson.content && 
                    !ideaJson.proposed_method && 
                    !ideaJson.experiment_plan && 
                    !ideaJson.test_case_examples) {
                    formattedContent += ideaJson.content;
                }
                
                console.log("Formatted content from JSON:", formattedContent.substring(0, 100) + "...");
                return formattedContent;
            }
        }
    } catch (e) {
        console.error("JSON parsing error:", e);
        console.log("Falling back to regex extraction...");
        
        // FALLBACK: Use regex extraction when JSON parsing fails
        try {
            // Extract sections using regex
            let formattedContent = "";
            
            // Extract title
            const titleMatch = ideaContent.match(/"title":\s*"([^"]+)"/);
            if (titleMatch && titleMatch[1]) {
                formattedContent += `# ${titleMatch[1]}\n\n`;
            } else {
                // Alternative match with single quotes
                const altTitleMatch = ideaContent.match(/'title':\s*'([^']+)'/);
                if (altTitleMatch && altTitleMatch[1]) {
                    formattedContent += `# ${altTitleMatch[1]}\n\n`;
                }
            }
            
            // Extract proposed method
            let proposedMethod = extractField(ideaContent, "proposed_method");
            if (proposedMethod) {
                formattedContent += `## Proposed Method\n\n${proposedMethod}\n\n***\n\n`;
            }
            
            // Extract experiment plan
            let experimentPlan = extractField(ideaContent, "experiment_plan");
            if (experimentPlan) {
                formattedContent += `## Experiment Plan\n\n${experimentPlan}\n\n***\n\n`;
            }
            
            // Extract test case examples
            let testCases = extractField(ideaContent, "test_case_examples");
            if (testCases) {
                formattedContent += `## Test Case Examples\n\n${testCases}\n\n`;
            }
            
            // If no structured fields were found, return the original content
            if (formattedContent === "" || formattedContent === "# \n\n") {
                console.log("No structured fields found with regex, returning original");
                return ideaContent;
            }
            
            console.log("Formatted content from regex:", formattedContent.substring(0, 100) + "...");
            return formattedContent;
        } catch (regexError) {
            console.error("Regex extraction failed:", regexError);
            // If regex extraction also fails, return original content
            return ideaContent;
        }
    }
    
    console.log("No JSON structure found, returning original");
    return ideaContent;
}

// Helper function to extract fields using regex
function extractField(content, fieldName) {
    // Try double quotes first
    const doubleQuotePattern = new RegExp(`"${fieldName}":\\s*"([^"]*(?:"[^"]*"[^"]*)*)"`);
    const doubleMatch = content.match(doubleQuotePattern);
    
    if (doubleMatch && doubleMatch[1]) {
        return doubleMatch[1].replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\\\/g, '\\');
    }
    
    // Try single quotes
    const singleQuotePattern = new RegExp(`'${fieldName}':\\s*'([^']*(?:'[^']*'[^']*)*)'`);
    const singleMatch = content.match(singleQuotePattern);
    
    if (singleMatch && singleMatch[1]) {
        return singleMatch[1].replace(/\\'/g, "'").replace(/\\n/g, '\n').replace(/\\\\/g, '\\');
    }
    
    // Try block approach - look for field followed by content between braces
    const blockPattern = new RegExp(`"${fieldName}":\\s*(\\{[^\\}]*\\}|\\[[^\\]]*\\])`);
    const blockMatch = content.match(blockPattern);
    
    if (blockMatch && blockMatch[1]) {
        return blockMatch[1];
    }
    
    // Try multi-line extraction (more complex but handles more cases)
    const multilinePattern = new RegExp(`"${fieldName}":\\s*"([\\s\\S]*?)(?:"\\s*,\\s*"(?:experiment_plan|proposed_method|test_case_examples|title)":|"\\s*\\})`);
    const multiMatch = content.match(multilinePattern);
    
    if (multiMatch && multiMatch[1]) {
        return multiMatch[1].replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\\\/g, '\\');
    }
    
    // If nothing works, return null
    return null;
}

function loadKnowledge() {
    $.get('/api/knowledge', function (data) {
        var list = $("#knowledge-list");
        list.empty();
        data.forEach(function (chunk) {
            var chunkDiv = $('<div class="knowledge-chunk"></div>');
            chunkDiv.text(chunk.text);
            // Create hover popup for full text
            var fullText = $('<div class="full-text"></div>');
            fullText.text(chunk.full_text);
            chunkDiv.append(fullText);
            // Append source link
            var link = $('<br/><a target="_blank" href="' + chunk.source + '">Source</a>');
            chunkDiv.append(link);
            list.append(chunkDiv);
        });
    });
}

function addKnowledge() {
    var text = prompt("Enter knowledge text:");
    var source = prompt("Enter source URL:");
    if (text && source) {
        $.ajax({
            url: '/api/add_knowledge',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ text: text, source: source }),
            success: function (data) {
                loadKnowledge();
            }
        });
    }
}

function loadChat() {
    $.get('/api/chat', function (data) {
        var chatArea = $("#chat-box");
        chatArea.empty();
        data.forEach(function (message) {
            var messageDiv = $('<div></div>')
                .attr('data-sender', message.role)
                .html(formatMessage(message.content));
            chatArea.append(messageDiv);
        });
        // Smooth scroll to bottom
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
    });
}

// Update loadIdea to preserve highlights and handle JSON structure
function loadIdea(isInitialLoad = false) {
    $.get('/api/idea', function (data) {
        if (data.idea) {
            // Store the raw idea
            highlightState.rawIdea = data.idea;
            
            // Store the idea in the global variable
            main_idea = data.idea;
            
            // Parse and format structured JSON if present
            const structuredContent = parseAndFormatStructuredIdea(data.idea);
            
            // If this is an initial load or there are no highlights yet, replace content
            if (isInitialLoad || highlightState.highlights.length === 0) {
                const formattedContent = formatMessage(structuredContent);
                $("#main-idea").html(formattedContent);
                highlightState.lastContent = $("#main-idea").html();
                $("#main-idea").show(); // Show the main idea panel
                $("#brief-placeholder").hide(); // Hide the placeholder
            }
            
            // Show review feedback if it exists (without removing highlights)
            if (data.review_feedback) {
                updateReviewFeedback(data.review_feedback);
            }
            
            // Handle score display
            updateReview(data);
        }
    });
}

// Update chat input placeholder and message handling
function sendMessage() {
    var input = $("#chat-input");
    var content = input.val().trim();
    if (content === "") return;

    // On first message, show proposal in sticky box and clear placeholder
    const isFirstMessage = $("#welcome-message").is(":visible");
    if (isFirstMessage) { // Check welcome message visibility instead of current_root
        // Update the proposal box content
        $("#welcome-message").hide();
        $("#proposal-content").show().text(content);
        $("#edit-button").show();
        
        // Change input placeholder for subsequent messages
        input.attr("placeholder", "Provide feedback or suggestions to refine your research idea...");
    }

    // Hide placeholder messages and show content areas
    $("#brief-placeholder").hide();
    $("#main-idea").show();

    // Disable input while processing
    input.prop('disabled', true);
    input.val('');

    // Add user message to chat ONLY if it's not the first message
    var chatArea = $("#chat-box");
    if (!isFirstMessage) {
        var userMessageDiv = $('<div></div>')
            .attr('data-sender', 'user')
            .text(content)
            .hide();
        chatArea.append(userMessageDiv);
        userMessageDiv.slideDown();
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
    }

    // Add loading indicator
    var loadingDiv = $('<div></div>')
        .attr('data-sender', 'system')
        .text('Processing...')
        .hide();
    chatArea.append(loadingDiv);
    loadingDiv.slideDown();
    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

    $.ajax({
        url: '/api/chat',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ content: content }),
        success: function (data) {
            // Remove loading indicator
            loadingDiv.remove();

            // Display system messages (like "Generating idea...")
            if (data.messages && data.messages.length > 0) {
                // Add all system messages that were added after user's message
                const userMessageIndex = data.messages.findIndex(m =>
                    m.role === 'user' && m.content === content);

                if (userMessageIndex !== -1) {
                    for (let i = userMessageIndex + 1; i < data.messages.length; i++) {
                        const msg = data.messages[i];
                        if (msg.role === 'system') {
                            var systemMsgDiv = $('<div></div>')
                                .attr('data-sender', 'system')
                                .text(msg.content)
                                .hide();
                            chatArea.append(systemMsgDiv);
                            systemMsgDiv.slideDown();
                        }
                    }
                }

                // Auto scroll to bottom
                chatArea.scrollTop(chatArea[0].scrollHeight);
            }

            // Update main idea if provided
            if (data.idea) {
                // Parse and format any JSON structure in the idea
                const structuredIdea = parseAndFormatStructuredIdea(data.idea);
                $("#main-idea").html(formatMessage(structuredIdea));
            }

            // Show research brief buttons after first response
            $(".research-brief-buttons").fadeIn();

            if (data.average_score !== undefined) {
                updateScoreDisplay(data.average_score);
            }
        },
        error: function (xhr, status, error) {
            // Remove loading indicator
            loadingDiv.remove();

            var errorDiv = $('<div></div>')
                .attr('data-sender', 'system')
                .text('Error: ' + (xhr.responseJSON?.error || error))
                .hide();
            chatArea.append(errorDiv);
            errorDiv.slideDown();
            chatArea.scrollTop(chatArea[0].scrollHeight);
        },
        complete: function () {
            // Re-enable input
            input.prop('disabled', false);
            input.focus();
        }
    });
}

// Add Enter key handler for chat input
$("#chat-input").keypress(function (e) {
    if (e.which == 13 && !e.shiftKey) {  // Enter without Shift
        e.preventDefault();
        sendMessage();
    }
});

//The function defined below uses the backend logic where the MCTS algorithm is implemented.
function toggleAutoGenerate() {
    const button = $(".auto-generate");
    
    if (button.hasClass("active")) {
        // Stop auto-generation
        button.removeClass("active");
        clearTimeout(window.autoGenerateTimer);
        window.autoGenerateTimer = null;
        mctsIterationCount = 0; // Reset counter
        
        // Add system message about stopping
        const chatArea = $("#chat-box");
        const stopMessage = $('<div></div>')
            .attr('data-sender', 'system')
            .text('🛑 MCTS exploration stopped.')
            .hide();
        chatArea.append(stopMessage);
        stopMessage.slideDown();
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

                // Make one final regular API call to trigger best child selection
        $.ajax({
            url: '/api/step',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ 
                action: 'generate',  // Use existing action
                use_mcts: false      // This will trigger the mcts_best_child logic
            }),
            success: function(data) {
                console.log('Final best child result:', data);
                
                // Update with the best idea found
                if (data.idea) {
                    const structuredIdea = parseAndFormatStructuredIdea ? 
                        parseAndFormatStructuredIdea(data.idea) : data.idea;
                    
                    $("#main-idea").html(formatMessage ? formatMessage(structuredIdea) : structuredIdea);
                    
                    if (typeof window !== 'undefined') {
                        window.main_idea = data.idea;
                    }
                    
                    $("#brief-placeholder").hide();
                    $("#main-idea").show();
                }
                
                // Update score display
                if (data.average_score !== undefined && typeof updateScoreDisplay === 'function') {
                    updateScoreDisplay(data.average_score);
                }
                
                // Show final result message
                const finalMessage = $('<div></div>')
                    .attr('data-sender', 'system')
                    .text(`🏆 Best idea selected from ${mctsIterationCount} iterations.`)
                    .hide();
                chatArea.append(finalMessage);
                finalMessage.slideDown();
                chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
                
                // Update tree visualization
                if (typeof loadTree === 'function') {
                    loadTree();
                }
            },
            error: function(xhr, status, error) {
                console.error('Error getting best child:', error);
                const errorMsg = $('<div></div>')
                    .attr('data-sender', 'system')
                    .text('❌ Error retrieving best result: ' + (xhr.responseJSON?.error || error))
                    .hide();
                chatArea.append(errorMsg);
                errorMsg.slideDown();
            },
            complete: function() {
                // Reset counter after everything is done
                mctsIterationCount = 0;
            }
        });
    } else {
        // Check if we have an idea to work with
        const mainIdea = $("#main-idea").text().trim();
        if (!mainIdea || mainIdea.length === 0) {
            alert("Please enter a research idea first before starting automated exploration.");
            return;
        }
        
        // Reset iteration counter and start auto-generation
        mctsIterationCount = 0;
        button.addClass("active");
        
        // Add system message about starting
        const chatArea = $("#chat-box");
        const startMessage = $('<div></div>')
            .attr('data-sender', 'system')
            .text(`🤖 Starting MCTS exploration (${MCTS_CONFIG.maxIterations} iterations)...`)
            .hide();
        chatArea.append(startMessage);
        startMessage.slideDown();
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
        
        // Define recursive function for continuous exploration
        function performMCTSStep() {
            // Check iteration limit using hyperparameters
            const shouldStop = !button.hasClass("active") || mctsIterationCount >= MCTS_CONFIG.maxIterations;
    
            if (shouldStop) {
                // Clear any pending timers
                if (window.autoGenerateTimer) {
                    clearTimeout(window.autoGenerateTimer);
                    window.autoGenerateTimer = null;
                }
                
                // Remove active class and show completion message
                button.removeClass("active");
                
                if (mctsIterationCount >= MCTS_CONFIG.maxIterations) {
                    const chatArea = $("#chat-box");
                    const completionMessage = $('<div></div>')
                        .attr('data-sender', 'system')
                        .text(`✅ MCTS exploration completed after ${mctsIterationCount} iterations.`)
                        .hide();
                    chatArea.append(completionMessage);
                    completionMessage.slideDown();
                    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
                }
                
                // Reset counter
                mctsIterationCount = 0;
                return;
            }
            
            // Increment iteration counter
            mctsIterationCount++;
            
            // Call the backend with the generate action and use_mcts flag
            $.ajax({
                url: '/api/step',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ 
                    action: 'generate', 
                    use_mcts: true,
                    num_iterations: 1,
                    iteration: mctsIterationCount,
                    max_iterations: MCTS_CONFIG.maxIterations
                }),
                success: function(data) {
                    console.log(`MCTS step ${mctsIterationCount}/${MCTS_CONFIG.maxIterations} response:`, data);
                    
                    // Update Research Brief panel
                    if (data.idea) {
                        const structuredIdea = parseAndFormatStructuredIdea ? 
                            parseAndFormatStructuredIdea(data.idea) : data.idea;
                        
                        $("#main-idea").html(formatMessage ? formatMessage(structuredIdea) : structuredIdea);
                        
                        // Update global variable
                        if (typeof window !== 'undefined') {
                            window.main_idea = data.idea;
                        }
                        
                        // Make sure Research Brief is visible
                        $("#brief-placeholder").hide();
                        $("#main-idea").show();
                    }
                    
                    // Update score display
                    if (data.average_score !== undefined && typeof updateScoreDisplay === 'function') {
                        updateScoreDisplay(data.average_score);
                    }
                    
                    // Update tree visualization if available
                    if (typeof loadTree === 'function') {
                        loadTree();
                    }
                    
                    // Schedule next step using hyperparameter delay
                    if (button.hasClass("active") && mctsIterationCount < MCTS_CONFIG.maxIterations) {
                        window.autoGenerateTimer = setTimeout(performMCTSStep, MCTS_CONFIG.explorationDelay);
                    } else {
                    // Force stop if conditions not met
                        performMCTSStep(); // This will trigger the stop logic
}
                },
                error: function(xhr, status, error) {
                    console.error('MCTS step error:', error);
                    
                    const chatArea = $("#chat-box");
                    const errorMsg = $('<div></div>')
                        .attr('data-sender', 'system')
                        .text('❌ Error in MCTS exploration: ' + (xhr.responseJSON?.error || error))
                        .hide();
                    chatArea.append(errorMsg);
                    errorMsg.slideDown();
                    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
                    
                    // Stop auto-generation on error
                    button.removeClass("active");
                    mctsIterationCount = 0;
                    if (window.autoGenerateTimer) {
                        clearTimeout(window.autoGenerateTimer);
                        window.autoGenerateTimer = null;
                    }
                }
            });
        }
        
        // Start the first MCTS step
        performMCTSStep();
    }
}

function stepAction(action) {
    // Get chat area for message display
    const chatArea = $("#chat-box");

    // Handle active state for buttons
    if (action === 'generate') {
        toggleAutoGenerate();
    } else if (action === 'judge') {
        // Add system message to indicate review generation is starting
        var loadingDiv = $('<div></div>')
            .attr('data-sender', 'system')
            .text('Generating review...')
            .hide();
        chatArea.append(loadingDiv);
        loadingDiv.slideDown();
        chatArea.scrollTop(chatArea[0].scrollHeight);

        const judgeButton = $(".top-bar button:nth-child(4)"); // Judge button
        judgeButton.toggleClass("active"); // Toggle active class

        // If the Judge button is active, remove active class from other buttons
        if (judgeButton.hasClass("active")) {
            $(".top-bar button").not(judgeButton).removeClass("active");
        }
    } else {
        // Remove active class from Auto and Judge buttons
        $(".auto-generate").removeClass("active"); // Auto button
        $(".top-bar button:nth-child(4)").removeClass("active"); // Judge button

        // Highlight Previous or Next button temporarily
        const buttonToHighlight = action === 'prev' ? $(".top-bar button:nth-child(2)") : $(".top-bar button:nth-child(3)");
        buttonToHighlight.addClass("active");

        // Remove highlight after a short delay
        setTimeout(function () {
            buttonToHighlight.removeClass("active");
        }, 500); // Adjust the duration as needed
    }

    $.ajax({
        url: '/api/step',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ action: action }),
        success: function (data) {
            // Update the main idea if provided
            if (data.idea) {
                // Parse and format any JSON structure in the idea
                const structuredIdea = parseAndFormatStructuredIdea(data.idea);
                $("#main-idea").html(formatMessage(structuredIdea));
            }

            // Update review scores if available
            updateReview(data);
            
            // Update chat messages if provided
            if (data.messages) {
                updateChat(data.messages);
            }

            if (data.average_score !== undefined) {
                updateScoreDisplay(data.average_score);
            }
        },
        error: function (xhr, status, error) {
            var errorDiv = $('<div></div>')
                .attr('data-sender', 'system')
                .text('Error: ' + (xhr.responseJSON?.error || error))
                .hide();
            chatArea.append(errorDiv);
            errorDiv.slideDown();
            chatArea.scrollTop(chatArea[0].scrollHeight);
        }
    });
}

function toggleTree() {
    treeMode = !treeMode;
    $("#chat-box").toggle(!treeMode);
    $("#tree-area").toggle(treeMode);
    // Fix: Target the tree button specifically (5th button) instead of using last()
    $(".top-bar button:nth-child(5)").toggleClass("active");
    if (treeMode) {
        loadTree();
    }
}

function loadTree() {
    // Show loading indicator
    $("#tree-area").html("<div class='loading'>Looking for ideas... 🔍</div>");
    
    // Fetch actual tree data from server
    $.ajax({
        url: "/api/tree",
        type: "GET",
        success: function(data) {
            if (data.state && data.state.current_idea) {
                // We have at least a root node
                treeData = transformTreeData(data);
                createTree(treeData);
            } else {
                // Show cute message when no ideas yet
                $("#tree-area").html(`
                    <div class='empty-tree-message'>
                        <div class='empty-tree-content'>
                            <div class='empty-tree-icon'>🌱</div>
                            <div class='empty-tree-text'>
                                Plant your first idea in the chat!
                                <br/>
                                <span class='empty-tree-subtext'>Watch it grow into a tree of ideas</span>
                            </div>
                        </div>
                    </div>
                `);
            }
        },
        error: function(error) {
            $("#tree-area").html("<div class='empty-tree-message'>Oops! My branches got tangled 🌿<br/>Let's try again!</div>");
            console.error("Error loading tree:", error);
        }
    });
}

// Transform API tree data into D3-friendly format
function transformTreeData(apiData) {
    function processNode(node) {
        // Check if this is a research goal node (special handling)
        const isResearchGoal = node.action === "research_goal" || 
                              (node.state && node.state.isResearchGoal === true);
        
        return {
            name: isResearchGoal ? "research_goal" : node.action,
            id: node.id,
            nodeData: {
                idea: node.state?.current_idea || node.idea,
                reward: node.reward || node.state?.reward,
                depth: node.depth || node.state?.depth,
                hasReviews: node.state?.hasReviews || false,
                hasRetrieval: node.state?.hasRetrieval || false,
                hasFeedback: node.state?.hasFeedback || false,
                isCurrentNode: node.isCurrentNode || false,
                reviews: node.reviews,
                isResearchGoal: isResearchGoal
            },
            children: node.children ? node.children.map(processNode) : []
        };
    }
    
    return processNode(apiData);
}

function createTree(data) {
    // Clear previous tree
    d3.select("#tree-area").html("");
    const margin = { top: 60, right: 40, bottom: 60, left: 40 };
    const width = document.getElementById('tree-area').offsetWidth - margin.left - margin.right;
    const height = document.getElementById('tree-area').offsetHeight - margin.top - margin.bottom;
    const svg = d3.select("#tree-area")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);
    const tree = d3.tree()
        .size([width, height * 0.8]);
    const root = d3.hierarchy(data);
    tree(root);
    const rootX = root.x;
    root.descendants().forEach(d => {
        d.x = d.x - rootX + width / 2;
    });
    // Add links with curved paths
    svg.selectAll(".link")
        .data(root.links())
        .join("path")
        .attr("class", "link")
        .attr("d", d3.linkVertical()
            .x(d => d.x)
            .y(d => d.y));
    // Add nodes group
    const nodes = svg.selectAll(".node")
        .data(root.descendants())
        .join("g")
        .attr("class", d => `node ${d.data.nodeData.isCurrentNode ? "current" : ""} ${d.data.nodeData.isResearchGoal ? "research-goal" : ""}`)
        .attr("transform", d => `translate(${d.x},${d.y})`)
        .on("click", function(event, d) {
            selectNode(d);
        });
    // Add node circles with colors based on action type
    nodes.append("circle")
        .attr("r", d => d.data.nodeData.isResearchGoal ? 12 : 8)  // Larger circle for research goal
        .attr("fill", d => {
            // Special color for research goal node
            if (d.data.nodeData.isResearchGoal) return "#3b82f6";  // Blue for research goal
            
            // Color nodes based on action type
            if (d.data.name === "root") return "#ffffff";
            if (d.data.name === "generate") return "#4ade80"; // green
            if (d.data.name === "reflect_and_reframe") return "#a78bfa"; // purple
            if (d.data.name === "review_and_refine") return "#fb923c"; // orange
            if (d.data.name === "retrieve_and_refine") return "#fbbf24"; // yellow
            if (d.data.name === "first_idea") return "#4ade80"; // green for first idea
            return "#3b82f6"; // default blue
        })
        .attr("stroke", d => d.data.nodeData.isResearchGoal ? "#2563eb" : "#3b82f6")
        .attr("stroke-width", d => d.data.nodeData.isResearchGoal ? 3 : 2.5);

    // Add indicators for nodes with reviews, retrieval or feedback
    const indicatorRadius = 3;
    const indicators = nodes.filter(d => 
        !d.data.nodeData.isResearchGoal && (
          d.data.nodeData.hasReviews || 
          d.data.nodeData.hasRetrieval || 
          d.data.nodeData.hasFeedback
        )
    );
    
    // Add indicators in a row under the node
    indicators.each(function(d) {
        const g = d3.select(this);
        let xOffset = -8;
        
        if (d.data.nodeData.hasReviews) {
            g.append("circle")
                .attr("cx", xOffset += 8)
                .attr("cy", 15)
                .attr("r", indicatorRadius)
                .attr("fill", "#fb923c")
                .attr("stroke", "#ffffff")
                .attr("stroke-width", 1);
        }
        
        if (d.data.nodeData.hasRetrieval) {
            g.append("circle")
                .attr("cx", xOffset += 8)
                .attr("cy", 15)
                .attr("r", indicatorRadius)
                .attr("fill", "#fbbf24")
                .attr("stroke", "#ffffff")
                .attr("stroke-width", 1);
        }
        
        if (d.data.nodeData.hasFeedback) {
            g.append("circle")
                .attr("cx", xOffset += 8)
                .attr("cy", 15)
                .attr("r", indicatorRadius)
                .attr("fill", "#a78bfa")
                .attr("stroke", "#ffffff")
                .attr("stroke-width", 1);
        }
    });
    // Add text labels showing action type
    nodes.append("text")
        .attr("dy", "25")
        .attr("y", 5) 
        .attr("text-anchor", "middle")
        .text(d => {
            const action = d.data.name;
            
            // Special label for research goal
            if (d.data.nodeData.isResearchGoal || action === "research_goal") {
                return "Research Goal";
            }
            
            // Shorten action names for display
            if (action === "root") return "Root";
            if (action === "generate") return "Gen";
            if (action === "first_idea") return "First Idea";
            if (action === "reflect_and_reframe") return "Reflect";
            if (action === "review_and_refine") return "Review";
            if (action === "retrieve_and_refine") return "Retrieve";
            if (action === "refresh_idea") return "Refresh";
            return action;
        })
        .each(function(d) {
            // Add background rectangle for text
            const bbox = this.getBBox();
            const padding = 2;
            
            d3.select(this.parentNode)
                .insert("rect", "text")
                .attr("x", bbox.x - padding)
                .attr("y", bbox.y - padding)
                .attr("width", bbox.width + (padding * 2))
                .attr("height", bbox.height + (padding * 2))
                .attr("fill", "#ffffff")
                .attr("fill-opacity", 0.9)
                .attr("rx", 4);
        });
    
    // Add highlight for current node
    nodes.filter(d => d.data.nodeData.isCurrentNode)
        .append("circle")
        .attr("r", 12)
        .attr("fill", "none")
        .attr("stroke", "#2563eb")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "3,3")
        .attr("class", "current-indicator");
        
    // Add CSS for research goal node
    const style = document.createElement('style');
    if (!document.getElementById('research-goal-style')) {
        style.id = 'research-goal-style';
        style.textContent = `
            .node.research-goal text {
                font-weight: bold;
                font-size: 1.1em;
            }
        `;
        document.head.appendChild(style);
    }
}

function selectNode(d) {
    // Node data is in d.data.nodeData from D3 hierarchy
    const nodeData = d.data;
    const nodeId = nodeData.id;
    
    // Send request to backend to select this node
    $.ajax({
        url: "/api/node",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ node_id: nodeId }),
        success: function(response) {
            // Update UI to reflect selected node
            // Parse and format any JSON structure in the idea
            if (response.idea) {
                const structuredIdea = parseAndFormatStructuredIdea(response.idea);
                $("#main-idea").html(marked.parse(structuredIdea));
            }
            
            // Reload tree to update visualization
            loadTree();
            
            // Add history entry
            const action = nodeData.name || "Unknown";
            $("#history-log").append(
                `<div class="history-item">Selected ${action} node (ID: ${nodeId})</div>`
            );
            
            // Scroll history to bottom
            const historyLog = document.getElementById("history-log");
            historyLog.scrollTop = historyLog.scrollHeight;
        },
        error: function(error) {
            console.error("Error selecting node:", error);
            alert("Error selecting node: " + (error.responseJSON?.error || "Unknown error"));
        }
    });
}

// Add refresh button handler for refreshing ideas with proper feedback
$(".refresh-button").click(function() {
    refreshResearchIdea();
});

// Create a dedicated function for refreshing research ideas
function refreshResearchIdea() {
    // Add feedback message to chat area first
    const chatArea = $("#chat-box");
    const loadingMessage = $('<div></div>')
        .attr('data-sender', 'system')
        .text('Refreshing your research idea...')
        .hide();
    
    chatArea.append(loadingMessage);
    loadingMessage.slideDown();
    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
    
    // Ensure we have the current idea text
    if (!main_idea) {
        main_idea = $("#main-idea").text();
    }
    
    console.log("Refreshing idea, current idea length:", main_idea.length);
    
    // Create dedicated API call for refresh
    $.ajax({
        url: "/api/refresh_idea",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ idea: main_idea }),
        success: function(response) {
            console.log("Refresh success, response received");
            console.log("Response idea length:", response.idea ? response.idea.length : 0);
            console.log("Response idea preview:", response.idea ? response.idea.substring(0, 100) + "..." : "No idea in response");
            
            // Remove loading message
            loadingMessage.remove();
            
            // Add success message
            const successMessage = $('<div></div>')
                .attr('data-sender', 'system')
                .text('Successfully refreshed your research idea!')
                .hide();
            chatArea.append(successMessage);
            successMessage.slideDown();
            
            // Update research brief with new idea - this is the critical part
            if (response.idea) {
                // Force update the main_idea variable
                main_idea = response.idea;
                
                // Force direct update to the research brief panel without parsing
                $("#main-idea").html(marked.parse(response.idea));
                
                console.log("Research brief updated with new content:", $("#main-idea").html().substring(0, 100) + "...");
                
                // Don't add the refreshed idea to the chat window
                // Only keep system messages in chat
            }
            
            // Update chat messages if any (only system messages)
            if (response.messages) {
                // Filter to only get system messages and not the full idea
                const systemMessages = response.messages.filter(msg => 
                    msg.role === 'system' || 
                    (msg.role === 'assistant' && msg.content.length < 500)
                );
                
                updateChat(systemMessages);
            }
            
            // Reload tree visualization
            if (typeof loadTree === 'function') {
                loadTree();
            }
            
            // Scroll chat to bottom
            chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
            
            // Update review scores if available
            if (response.review_scores && response.average_score) {
                updateScoreDisplay(response.review_scores, response.average_score);
            }
        },
        error: function(error) {
            console.error("Error refreshing idea:", error);
            
            // Remove loading message
            loadingMessage.remove();
            
            // Show error message
            const errorMessage = $('<div></div>')
                .attr('data-sender', 'system')
                .text('Error refreshing idea: ' + (error.responseJSON?.error || "An error occurred"))
                .hide();
            chatArea.append(errorMessage);
            errorMessage.slideDown();
            chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
        }
    });
}

// Add window resize handler
$(window).resize(function () {
    if (treeMode && treeData) {
        createTree(treeData);
    }
});

// Add this function to handle the edit button click
$("#edit-button").click(function () {
    // Create and show the custom editor popup
    createEditorPopup("Edit Research Proposal", $("#proposal-content").text(), function(newText) {
        if (newText.trim() !== "") {
            // Update the proposal content
            $("#proposal-content").text(newText);
        }
    });
});

// Create custom editor popup function
function createEditorPopup(title, content, saveCallback) {
    // Create overlay
    const overlay = $('<div class="editor-popup-overlay"></div>');
    
    // Create popup structure
    const popup = $(`
        <div class="editor-popup">
            <div class="editor-popup-header">
                <div class="editor-popup-title">${title}</div>
                <button class="editor-popup-close">&times;</button>
            </div>
            <div class="editor-popup-body">
                <textarea class="editor-popup-textarea">${content}</textarea>
            </div>
            <div class="editor-popup-footer">
                <button class="editor-popup-button editor-cancel-button">Cancel</button>
                <button class="editor-popup-button editor-save-button">Save</button>
            </div>
        </div>
    `);
    
    // Add to DOM
    overlay.append(popup);
    $('body').append(overlay);
    
    // Focus on textarea
    const textarea = popup.find('.editor-popup-textarea');
    textarea.focus();
    
    // Position cursor at the end of text
    const textLength = textarea.val().length;
    textarea[0].setSelectionRange(textLength, textLength);
    
    // Close handlers
    function closePopup() {
        overlay.remove();
    }
    
    popup.find('.editor-popup-close, .editor-cancel-button').click(closePopup);
    
    // Save handler
    popup.find('.editor-save-button').click(function() {
        const newContent = textarea.val();
        saveCallback(newContent);
        closePopup();
    });
    
    // Close on escape key
    $(document).on('keydown.editorPopup', function(e) {
        if (e.key === 'Escape') {
            closePopup();
            $(document).off('keydown.editorPopup');
        }
    });
    
    // Prevent closing when clicking inside popup
    popup.click(function(e) {
        e.stopPropagation();
    });
    
    // Close when clicking on overlay
    overlay.click(closePopup);
}

// Update handleReviewAction function
// function handleReviewAction(action) {
//     if (!$("#review-feedback").is(":visible")) {
//         $("#review-feedback").show();
//     }
//     if (action === 'fix') {
//         // In the future this will trigger the fix workflow
//         console.log('Fixing review issue');
//         stepAction('generate');  // For now just trigger generate
//     } else {
//         // Maybe store that this issue was ignored
//         console.log('Ignoring review issue');
//     }
// }

// Add new function for the Generate Review button
$(".generate-review").click(function () {
    // Reset review state
    currentReviewAspectIndex = 0;
    acceptedReviews = [];
    reviewInProgress = true;

    // Clear any existing highlights
    cleanupPreviousHighlights();

    // Add a loading message to chat
    const chatArea = $("#chat-box");
    const loadingMessage = $('<div></div>')
        .attr('data-sender', 'system')
        .text('Starting structured review... Evaluating ' + aspectsToReview[0])
        .hide();
    chatArea.append(loadingMessage);
    loadingMessage.slideDown();
    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

    // Start the review process
    requestAspectReview(0);
});

// Function to request review for a specific aspect
function requestAspectReview(aspectIndex) {
    console.log("Requesting review for aspect index:", aspectIndex);
    
    if (aspectIndex >= state.aspectsToReview.length) {
        // Review process complete
        const chatArea = $("#chat-box");
        const completionMessage = $('<div></div>')
            .attr('data-sender', 'system')
            .text('Review process complete. Please review each suggestion and accept or reject them.')
            .hide();

        chatArea.append(completionMessage);
        completionMessage.slideDown();
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

        state.reviewInProgress = false;
        return;
    }

    // Get the current research idea text
    const ideaText = $("#main-idea").text();
    console.log("Current idea text:", ideaText);

    $.ajax({
        url: '/api/review_aspect',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            idea: ideaText,
            aspect: state.aspectsToReview[aspectIndex],
            aspect_index: aspectIndex
        }),
        success: function(data) {
            console.log("Review data received:", data);
            if (data.review_data) {
                displayAspectReview(data.review_data);
                
                // Move to next aspect after a delay
                setTimeout(() => {
                    state.currentReviewAspectIndex++;
                    requestAspectReview(state.currentReviewAspectIndex);
                }, 3000);
            } else {
                console.error("No review data received");
                // Continue to next aspect
                state.currentReviewAspectIndex++;
                requestAspectReview(state.currentReviewAspectIndex);
            }
        },
        error: function(xhr, status, error) {
            console.error("Review request error:", error);
            
            const chatArea = $("#chat-box");
            const errorMessage = $('<div></div>')
                .attr('data-sender', 'system')
                .text('Error: ' + (xhr.responseJSON?.error || error))
                .hide();
            chatArea.append(errorMessage);
            errorMessage.slideDown();
            chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

            // Continue with next aspect despite error
            state.currentReviewAspectIndex++;
            requestAspectReview(state.currentReviewAspectIndex);
        }
    });
}

// Function to display review for a specific aspect
function displayAspectReview(reviewData) {
    const mainIdea = $('#main-idea');
    console.log("Displaying review for aspect:", reviewData);
    
    // Add dynamic CSS for highlights
    addHighlightStyles(reviewData.aspect);
    
    // Clear previous highlights for current aspect
    clearHighlightsForAspect(reviewData.aspect);

    // Get the current text content
    let currentText = mainIdea.html() || mainIdea.text();
    
    // Add debugging for the text matching issue
    console.log("Review highlight text:", reviewData.highlights && reviewData.highlights.length > 0 ? 
                reviewData.highlights[0].text : "No highlights found");
                
    // Apply highlights if they exist
    if (reviewData.highlights && reviewData.highlights.length > 0) {
        reviewData.highlights.forEach(highlight => {
            console.log("Processing highlight:", highlight);
            
            // Find the exact text to highlight
            const text = highlight.text;
            console.log("Searching for text:", text);
            
            // Try direct string matching first (case sensitive)
            const index = currentText.indexOf(text);
            
            if (index !== -1) {
                console.log("Found exact match at position:", index);
                
                // Create the highlight span, preserving the exact text as-is
                const highlightSpan = `<span class="review-highlight ${reviewData.aspect}" 
                    data-aspect="${reviewData.aspect}"
                    data-category="${highlight.category}"
                    data-review="${escape(highlight.review)}">${text}</span>`;
                
                // Replace the text with highlighted version
                currentText = currentText.substring(0, index) + 
                             highlightSpan + 
                             currentText.substring(index + text.length);
                
                console.log("Highlight applied successfully");
            } else {
                // Fall back to case-insensitive search
                console.log("Exact match not found, trying case-insensitive match");
                const lowerText = currentText.toLowerCase();
                const lowerSearchText = text.toLowerCase();
                const lowerIndex = lowerText.indexOf(lowerSearchText);
                
                if (lowerIndex !== -1) {
                    console.log("Found case-insensitive match at position:", lowerIndex);
                    
                    // Extract the actual text with its original case/format
                    const actualText = currentText.substring(lowerIndex, lowerIndex + text.length);
                    
                    // Create the highlight span with the original text preserved
                    const highlightSpan = `<span class="review-highlight ${reviewData.aspect}" 
                        data-aspect="${reviewData.aspect}"
                        data-category="${highlight.category}"
                        data-review="${escape(highlight.review)}">${actualText}</span>`;
                    
                    // Replace the text with highlighted version
                    currentText = currentText.substring(0, lowerIndex) + 
                                 highlightSpan + 
                                 currentText.substring(lowerIndex + actualText.length);
                                 
                    console.log("Highlight applied with original case preserved");
                } else {
                    // Neither exact nor case-insensitive match found
                    console.log("No match found for text:", text);
                }
            }
        });
        
        // Update the content
        mainIdea.html(currentText);
        
        // Add click handlers
        addHighlightClickHandlers();
        
        // Show review summary in chat
        const chatArea = $("#chat-box");
        const summaryCard = $('<div class="review-summary-card"></div>')
            .html(`
                <div class="review-header">
                    <span class="aspect-badge ${reviewData.aspect}">${reviewData.aspect.toUpperCase()}</span>
                    <span class="score">Score: ${reviewData.score}/10</span>
                </div>
                <div class="summary">${reviewData.summary || ''}</div>
            `)
            .hide();
        
        chatArea.append(summaryCard);
        summaryCard.slideDown();
        
        // Show individual highlights in chat
        reviewData.highlights.forEach(highlight => {
            showReviewInChat(
                highlight.category,
                highlight.review,
                reviewData.aspect,
                null
            );
        });
    }
}

// Add new helper function for highlight styles
function addHighlightStyles(aspect) {
    const style = document.createElement('style');
    
    // Color palette for different aspects
    const colors = {
        'novelty': '#fff3cd',          // Light yellow
        'feasibility': '#d4edda',      // Light green
        'clarity': '#cfe2ff',          // Light blue
        'impact': '#f8d7da',           // Light red
        'methodology': '#e2e3e5',      // Light gray
        'assumptions': '#d1e7dd',      // Mint green
        'vagueness': '#d7f5fc',        // Light cyan
        'lack_of_novelty': '#fff3cd',  // Light yellow
        'reproducibility': '#e7d8fc'    // Light purple
    };
    
    // Default color for aspects not in our mapping
    const defaultColor = '#f8f9fa';
    
    // Get color for current aspect, or use default
    const color = colors[aspect] || defaultColor;
    
    style.textContent = `
        /* Highlight styles for text */
        .review-highlight.${aspect} {
            background-color: ${color};
            cursor: pointer;
            padding: 2px 4px;
            border-radius: 3px;
            transition: background-color 0.2s;
        }
        
        .review-highlight.${aspect}:hover {
            filter: brightness(0.95);
        }
        
        /* Badge and score styles for review cards */
        .aspect-badge.${aspect}, 
        .review-card:has(.aspect-badge.${aspect}) .aspect-score {
            background-color: ${color};
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }
    `;
    
    document.head.appendChild(style);
}

// Update showReviewInChat to be more visually appealing
function showReviewInChat(category, description, aspect, highlightElement) {
    const chatArea = $("#chat-box");
    
    const reviewCard = $('<div class="review-card"></div>')
        .html(`
            <div class="review-card-header">
                <span class="aspect-badge ${aspect}">${aspect}</span>
                <span class="category">${category}</span>
            </div>
            <div class="review-card-body">${description}</div>
            <div class="review-card-actions">
                <button class="accept-btn" title="Accept">
                    <img src="/static/icons/tick.svg" alt="Accept">
                </button>
                <button class="reject-btn" title="Reject">
                    <img src="/static/icons/cross.svg" alt="Reject">
                </button>
            </div>
        `)
        .hide();

    // Add click handlers for buttons
    reviewCard.find('.accept-btn').click(function() {
        acceptReview(aspect, category, description, highlightElement);
        reviewCard.slideUp();
    });

    reviewCard.find('.reject-btn').click(function() {
        rejectReview(highlightElement);
        reviewCard.slideUp();
    });

    chatArea.append(reviewCard);
    reviewCard.slideDown();
    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
}

// Add handler for accepting reviews
function acceptReview(aspect, category, review, highlightElement) {
    state.acceptedReviews.push({
        aspect: aspect,
        category: category,
        review: review
    });
    
    // Update highlight if it exists
    if (highlightElement) {
        $(highlightElement).addClass('accepted');
    }
}

// Add handler for rejecting reviews
function rejectReview(highlightElement) {
    if (highlightElement) {
        $(highlightElement).addClass('rejected');
    }
}

// Function to improve the idea based on accepted reviews
function improveIdeaBasedOnReviews() {
    if (state.acceptedReviews.length === 0) {
        const chatArea = $("#chat-box");
        chatArea.append(
            $('<div></div>')
                .attr('data-sender', 'system')
                .text('No review suggestions were accepted. Please accept some suggestions to improve the idea.')
        );
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
        return;
    }

    const ideaText = $("#main-idea").text();
    const chatArea = $("#chat-box");
    const loadingMessage = $('<div></div>')
        .attr('data-sender', 'system')
        .text('Improving idea based on accepted feedback...')
        .hide();
    chatArea.append(loadingMessage);
    loadingMessage.slideDown();
    chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

    $.ajax({
        url: '/api/improve_idea',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            idea: ideaText,
            accepted_reviews: state.acceptedReviews
        }),
        success: function (data) {
            loadingMessage.remove();

            // The backend returns improved_idea in the response
            const improvedIdea = data.improved_idea;
            
            if (improvedIdea) {
                // Add success message to chat
                const successMessage = $('<div></div>')
                    .attr('data-sender', 'system')
                    .text('Idea improved successfully based on accepted feedback.')
                    .hide();
                chatArea.append(successMessage);
                successMessage.slideDown();

                // CRITICAL: Update the global main_idea variable
                window.main_idea = improvedIdea;
                
                // Update the main idea display with proper formatting
                const formattedContent = formatMessage(improvedIdea);
                $("#main-idea").html(formattedContent);

                // Reset review state
                state.acceptedReviews = [];
                
                // Update visualizations
                if (typeof loadTree === 'function') {
                    loadTree();
                }

                if (data.average_score !== undefined) {
                    updateScoreDisplay(data.average_score);
                }
            } else {
                const errorMessage = $('<div></div>')
                    .attr('data-sender', 'system')
                    .text('Error improving idea: ' + (data.error || 'Unknown error'))
                    .hide();
                chatArea.append(errorMessage);
                errorMessage.slideDown();
            }
            chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
        },
        error: function (xhr, status, error) {
            loadingMessage.remove();
            const errorMessage = $('<div></div>')
                .attr('data-sender', 'system')
                .text('Error: ' + (xhr.responseJSON?.error || error))
                .hide();
            chatArea.append(errorMessage);
            errorMessage.slideDown();
            chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
        }
    });
}

// Helper function to escape HTML special characters
function escape(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

// Helper function to unescape HTML special characters
function unescape(str) {
    const div = document.createElement('div');
    div.innerHTML = str;
    return div.textContent;
}

// Add CSS for accepted highlights
function addCssRules() {
    const style = document.createElement('style');
    style.textContent = `
        .review-highlight.accepted {
            background-color: rgba(134, 239, 172, 0.4); /* light green */
            cursor: default;
        }
        .review-highlight.accepted:hover {
            background-color: rgba(134, 239, 172, 0.4); /* prevent hover effect */
        }
    `;
    document.head.appendChild(style);
}

// Call this on document ready
$(document).ready(function() {
    // ...existing code...
    addCssRules();
    
    // DO NOT attach event handlers here - the review-integration.js handles these
    // The click handler for Generate Review button is now defined in review-integration.js
    
    // Any other initialization code...
});

// Update requestAspectReview to use the state object
function requestAspectReview(aspectIndex) {
    console.log("Requesting review for aspect index:", aspectIndex);
    
    if (aspectIndex >= state.aspectsToReview.length) {
        // Review process complete
        const chatArea = $("#chat-box");
        const completionMessage = $('<div></div>')
            .attr('data-sender', 'system')
            .text('Review process complete. Please review each suggestion and accept or reject them.')
            .hide();

        chatArea.append(completionMessage);
        completionMessage.slideDown();
        chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

        state.reviewInProgress = false;
        return;
    }

    // Get the current research idea text
    const ideaText = $("#main-idea").text();
    console.log("Current idea text:", ideaText);

    $.ajax({
        url: '/api/review_aspect',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            idea: ideaText,
            aspect: state.aspectsToReview[aspectIndex],
            aspect_index: aspectIndex
        }),
        success: function(data) {
            console.log("Review data received:", data);
            if (data.review_data) {
                displayAspectReview(data.review_data);
                
                // Move to next aspect after a delay
                setTimeout(() => {
                    state.currentReviewAspectIndex++;
                    requestAspectReview(state.currentReviewAspectIndex);
                }, 3000);
            } else {
                console.error("No review data received");
                // Continue to next aspect
                state.currentReviewAspectIndex++;
                requestAspectReview(state.currentReviewAspectIndex);
            }
        },
        error: function(xhr, status, error) {
            console.error("Review request error:", error);
            
            const chatArea = $("#chat-box");
            const errorMessage = $('<div></div>')
                .attr('data-sender', 'system')
                .text('Error: ' + (xhr.responseJSON?.error || error))
                .hide();
            chatArea.append(errorMessage);
            errorMessage.slideDown();
            chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');

            // Continue with next aspect despite error
            state.currentReviewAspectIndex++;
            requestAspectReview(state.currentReviewAspectIndex);
        }
    });
}

// Update other functions to use state
function acceptReview(aspect, category, review, highlightElement) {
    state.acceptedReviews.push({
        aspect: aspect,
        category: category,
        review: review
    });
    
    if (highlightElement) {
        $(highlightElement).addClass('accepted');
    }
}

// ...rest of existing code...

// Make sure helper functions are properly defined
function cleanupPreviousHighlights() {
    const mainIdea = $('#main-idea');
    const content = mainIdea.html();
    if (content) {
        mainIdea.html(content.replace(/<span class="review-highlight[^>]*>(.*?)<\/span>/g, '$1'));
    }
}

function clearHighlightsForAspect(aspect) {
    const mainIdea = $('#main-idea');
    const content = mainIdea.html();
    if (content) {
        mainIdea.html(content.replace(
            new RegExp(`<span class="review-highlight ${aspect}"[^>]*>(.*?)<\/span>`, 'g'), 
            '$1'
        ));
    }
}

// Add this direct update function at the top of the file, to ensure it's available for all other functions
function forceUpdateScoreDisplay(score) {
    if (score === undefined || score === null) {
        return; // Don't update if no score is provided
    }
    
    console.log("Forcing score update to:", score);
    
    // Get DOM elements
    const scoreDisplay = document.getElementById('score-display');
    const scoreValue = document.getElementById('current-score');
    
    // Safety check
    if (!scoreDisplay || !scoreValue) {
        console.error("Score display elements not found in the DOM");
        return;
    }
    
    // Update the score text with 2 decimal places
    scoreValue.textContent = `${parseFloat(score).toFixed(2)}/10`;
    
    // Ensure the score display is visible
    scoreDisplay.style.display = 'block';
    
    // Add a flash animation
    scoreValue.classList.add('score-flash');
    setTimeout(() => scoreValue.classList.remove('score-flash'), 500);
}

// Now update the original function to use our direct update function
function updateScoreDisplay(score) {
    forceUpdateScoreDisplay(score);
}

// Function to update score display
function updateScoreDisplay(score) {
    forceUpdateScoreDisplay(score);
}

// Add to the success handlers of API calls
$.ajax({
    url: '/api/chat',
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
        content: messageContent
    }),
    success: function(data) {
        // ...existing success handler code...
        if (data.average_score !== undefined) {
            updateScoreDisplay(data.average_score);
        }
    },
    // ...rest of ajax code...
});

// Update score in other relevant API calls
$.ajax({
    url: '/api/step',
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
        action: action
    }),
    success: function(data) {
        // ...existing success handler code...
        if (data.average_score !== undefined) {
            updateScoreDisplay(data.average_score);
        }
    },
    // ...rest of ajax code...
});

// $.ajax({
//     url: '/api/improve_idea',
//     type: 'POST',
//     contentType: 'application/json',
//     data: JSON.stringify({
//         idea: ideaText,
//         accepted_reviews: state.acceptedReviews
//     }),
//     success: function(data) {
//         // ...existing success handler code...
//         if (data.average_score !== undefined) {
//             updateScoreDisplay(data.average_score);
//         }
//     },
//     // ...rest of ajax code...
// });

$.ajax({
    url: '/api/improve_idea_with_knowledge',
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
        idea: idea,
        // ...other data...
    }),
    success: function(data) {
        // ...existing success handler code...
        if (data.average_score !== undefined) {
            updateScoreDisplay(data.average_score);
        }
    },
    // ...rest of ajax code...
});

// Also update score when loading idea
function loadIdea(isInitialLoad = false) {
    $.ajax({
        url: '/api/idea',
        type: 'GET',
        success: function(data) {
            // ...existing success handler code...
            if (data.average_score !== undefined) {
                updateScoreDisplay(data.average_score);
            }
        },
        // ...rest of ajax code...
    });
}

// Add to existing event listeners
document.addEventListener('DOMContentLoaded', function() {
    // ...existing initialization code...
    
    // Initialize MCTS automation button state
    const autoGenBtn = document.querySelector('.auto-generate');
    if (autoGenBtn) {
        autoGenBtn.addEventListener('click', function(e) {
            e.preventDefault();
            toggleAutoGenerate();
        });
    }
});

// Add these functions to handle state updates
function updateScore(score) {
    const scoreDisplay = document.getElementById('current-score');
    if (scoreDisplay) {
        const oldScore = parseFloat(scoreDisplay.textContent);
        scoreDisplay.textContent = `${score.toFixed(1)}/10`;
        
        // Add animation class if score improved
        if (score > oldScore) {
            scoreDisplay.classList.add('score-flash');
            setTimeout(() => scoreDisplay.classList.remove('score-flash'), 500);
        }
    }
}

function updateMainIdea(content) {
    const mainIdea = document.getElementById('main-idea');
    if (mainIdea) {
        mainIdea.style.display = 'block';
        mainIdea.innerHTML = marked.parse(content);
        document.getElementById('brief-placeholder').style.display = 'none';
    }
}

// Update chat box with exploration status
function addExplorationMessage(message, isLoading = false) {
    const messageDiv = document.createElement('div');
    messageDiv.setAttribute('data-sender', 'system');
    
    if (isLoading) {
        messageDiv.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <div class="loading-text">${message}</div>
            </div>`;
    } else {
        messageDiv.textContent = message;
    }
    
    const chatBox = document.getElementById('chat-box');
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return messageDiv;
}

// Add error handling for API calls
function handleApiError(error, context) {
    console.error(`Error in ${context}:`, error);
    addExplorationMessage(`Error: ${error.message || 'An error occurred during exploration'}`, false);
    mctsAuto.stopExploration();
}

// Add WebSocket handling if using real-time updates
let explorationSocket = null;

function setupWebSocket() {
    if (!explorationSocket || explorationSocket.readyState !== WebSocket.OPEN) {
        explorationSocket = new WebSocket(getWebSocketUrl());
        
        explorationSocket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            handleExplorationUpdate(data);
        };
        
        explorationSocket.onerror = function(error) {
            console.error('WebSocket error:', error);
            handleApiError(error, 'WebSocket connection');
        };
    }
}

function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/exploration`;
}

function handleExplorationUpdate(data) {
    switch (data.type) {
        case 'progress':
            addExplorationMessage(data.message, data.isLoading);
            break;
        case 'score':
            updateScore(data.score);
            break;
        case 'idea':
            updateMainIdea(data.content);
            break;
        case 'complete':
            mctsAuto.stopExploration();
            addExplorationMessage('Exploration completed!');
            break;
        case 'error':
            handleApiError(new Error(data.message), 'Exploration update');
            break;
    }
}

// Add MCTS visualization support
function updateTreeVisualization(treeData) {
    const treeArea = document.getElementById('tree-area');
    if (!treeArea || treeArea.style.display === 'none') return;
    
    // Clear existing visualization
    treeArea.innerHTML = '';
    
    if (!treeData || !treeData.nodes || treeData.nodes.length === 0) {
        treeArea.innerHTML = `
            <div class="empty-tree-message">
                <div class="empty-tree-content">
                    <div class="empty-tree-icon">🌱</div>
                    <div class="empty-tree-text">No exploration data yet</div>
                    <div class="empty-tree-subtext">Start the automated exploration to see the search tree grow</div>
                </div>
            </div>`;
            }
    // Set up D3 visualization
    const width = treeArea.clientWidth;
    const height = treeArea.clientHeight;
    
    const svg = d3.select(treeArea)
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    const g = svg.append('g')
        .attr('transform', `translate(${width/2},50)`);
    
    // Create tree layout
    const treeLayout = d3.tree()
        .size([width - 100, height - 100]);
    
    const root = d3.hierarchy(treeData);
    treeLayout(root);
    
    // Add links
    g.selectAll('.link')
        .data(root.links())
        .enter()
        .append('path')
        .attr('class', 'link')
        .attr('d', d3.linkVertical()
            .x(d => d.x)
            .y(d => d.y));
    
    // Add nodes
    const nodes = g.selectAll('.node')
        .data(root.descendants())
        .enter()
        .append('g')
        .attr('class', d => `node${d.data.isCurrent ? ' current' : ''}`)
        .attr('transform', d => `translate(${d.x},${d.y})`);
    
    nodes.append('circle')
        .attr('r', 8)
        .attr('fill', d => getNodeColor(d.data));
    
    nodes.append('text')
        .attr('dy', '2em')
        .attr('text-anchor', 'middle')
        .text(d => d.data.score ? `${(d.data.score * 10).toFixed(1)}` : '');
}

function getNodeColor(nodeData) {
    if (nodeData.isCurrent) return '#3b82f6';
    if (nodeData.score > 0.7) return '#22c55e';
    if (nodeData.score > 0.4) return '#eab308';
    return '#64748b';
}

// Export functions that need to be accessible globally
window.updateScore = updateScore;
window.updateMainIdea = updateMainIdea;
window.addExplorationMessage = addExplorationMessage;
window.updateTreeVisualization = updateTreeVisualization;

// Add helper functions for automated button clicks
function triggerRetrieveKnowledge() {
    // Simulate click on retrieve button
    const retrieveBtn = document.querySelector(".retrieve-knowledge");
    if (retrieveBtn) {
        retrieveBtn.click();
        return true;
    }
    return false;
}

function triggerRefreshIdea() {
    // Simulate click on refresh button  
    const refreshBtn = document.querySelector(".refresh-button");
    if (refreshBtn) {
        refreshBtn.click();
        return true;
    }
    return false;
}

// // Update toggleAutoGenerate to use the trigger functions
// function toggleAutoGenerate() {
//     const autoButton = $(".auto-generate");
//     autoButton.toggleClass("active");
    
//     // If the Auto button is active, remove active class from other buttons
//     if (autoButton.hasClass("active")) {
//         $(".top-bar button").not(autoButton).removeClass("active");
        
//         // Get available actions with their trigger functions
//         const availableActions = [
//             {
//                 button: ".generate-review",
//                 action: "judge",
//                 trigger: () => window.triggerGenerateReview()
//             },
//             {
//                 button: ".retrieve-knowledge", 
//                 action: "retrieve_and_refine",
//                 trigger: triggerRetrieveKnowledge
//             },
//             {
//                 button: ".refresh-button",
//                 action: "refresh_idea", 
//                 trigger: triggerRefreshIdea
//             }
//         ];

//         // For now, randomly select one action
//         const randomAction = availableActions[Math.floor(Math.random() * availableActions.length)];
//         updateChat("🤖 " + "Taking action " + randomAction);
        
//         // Call the appropriate trigger function
//         if (randomAction.trigger()) {
//             // Send the corresponding action to backend
//             $.ajax({
//                 url: '/api/step',
//                 type: 'POST',
//                 contentType: 'application/json',
//                 data: JSON.stringify({ action: randomAction.action }),
//                 success: function (data) {
//                     // Update the main idea if provided
//                     if (data.idea) {
//                         const structuredIdea = parseAndFormatStructuredIdea(data.idea);
//                         $("#main-idea").html(formatMessage(structuredIdea));
//                     }

//                     // Update chat messages if provided
//                     if (data.messages) {
//                         updateChat(data.messages);
//                     }

//                     if (data.average_score !== undefined) {
//                         updateScoreDisplay(data.average_score);
//                     }
                    
//                     // If auto mode is still active, schedule next action
//                     if (autoButton.hasClass("active")) {
//                         setTimeout(toggleAutoGenerate, 5000); // 5 second delay between actions
//                     }
//                 },
//                 error: function(xhr, status, error) {
//                     const chatArea = $("#chat-box");
//                     var errorDiv = $('<div></div>')
//                         .attr('data-sender', 'system')
//                         .text('Error: ' + (xhr.responseJSON?.error || error))
//                         .hide();
//                     chatArea.append(errorDiv);
//                     errorDiv.slideDown();
//                     chatArea.scrollTop(chatArea[0].scrollHeight);
                    
//                     // Stop auto mode on error
//                     autoButton.removeClass("active");
//                 }
//             });
//         }
//     }
    
//     // Prevent the click from triggering other handlers
//     return false;
// }

// Add CSS for score display
function addScoreDisplayStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .score-display {
            position: absolute;
            top: 20px;
            right: 20px;
            background-color: #f0f9ff;
            border: 1px solid #bae6fd;
            border-radius: 8px;
            padding: 5px 10px;
            font-size: 14px;
            font-weight: bold;
            color: #0284c7;
            z-index: 100;
        }
        
        #current-score {
            font-size: 16px;
        }
        
        .score-flash {
            animation: score-flash-animation 0.5s;
        }
        
        @keyframes score-flash-animation {
            0% { background-color: #f0f9ff; }
            50% { background-color: #bae6fd; }
            100% { background-color: #f0f9ff; }
        }
    `;
    document.head.appendChild(style);
}

// Add this function to properly handle review data
function updateReview(data) {
    // Check if we have review scores and update the display
    if (data.average_score !== undefined) {
        updateScoreDisplay(data.average_score);
    }
    
    // Handle other review data if needed
    if (data.review_scores) {
        // Could add additional functionality here like showing detailed scores
        console.log("Review scores received:", data.review_scores);
    }
    
    if (data.review_feedback) {
        // Could handle detailed feedback here
        console.log("Review feedback received");
    }
}

window.toggleAutoGenerate = toggleAutoGenerate;