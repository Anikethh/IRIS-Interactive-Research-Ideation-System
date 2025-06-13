// // MCTS Automated Exploration Module for IRIS
// // This module implements automated idea exploration using MCTS algorithm

// // Import utility functions if they don't exist in the global scope
// if (typeof formatMessage !== 'function') {
//     function formatMessage(content) {
//         if (!content) return '';
//         // Ensure markdown rendering if marked library is available
//         if (typeof marked !== 'undefined') {
//             return marked.parse(content);
//         }
//         return content;
//     }
// }

// if (typeof updateChat !== 'function') {
//     function updateChat(messages) {
//         if (!messages || !messages.length) return;
        
//         const chatBox = $("#chat-box");
//         // Append new messages
//         messages.forEach(msg => {
//             if (msg.role && msg.content) {
//                 const messageDiv = $('<div></div>')
//                     .attr('data-sender', msg.role)
//                     .html(formatMessage(msg.content));
//                 chatBox.append(messageDiv);
//             }
//         });
        
//         // Scroll to bottom
//         chatBox.scrollTop(chatBox[0].scrollHeight);
//     }
// }

// if (typeof updateScoreDisplay !== 'function') {
//     function updateScoreDisplay(score) {
//         if (!score && score !== 0) return;
        
//         // Find or create the score display element
//         let scoreElement = $(".score-display");
//         if (scoreElement.length === 0) {
//             scoreElement = $('<div class="score-display"></div>');
//             $("#main-idea-container").prepend(scoreElement);
//         }
        
//         // Update the score with 2 decimal places
//         const scoreValue = parseFloat(score).toFixed(2);
//         scoreElement.html(`<span class="score-label">Score:</span> <span class="score-value">${scoreValue}</span>`);
        
//         // Apply color based on score
//         if (scoreValue >= 8.0) {
//             scoreElement.removeClass().addClass('score-display high-score');
//         } else if (scoreValue >= 6.0) {
//             scoreElement.removeClass().addClass('score-display medium-score');
//         } else {
//             scoreElement.removeClass().addClass('score-display low-score');
//         }
//     }
// }

// const mctsAuto = {
//     // Configuration
//     isRunning: false,
//     maxIterations: 5,
//     currentIteration: 0,
//     explorationDelay: 3000,
//     explorationConstant: 1.414,  // Same as backend UCT exploration parameter
//     discountFactor: 0.95,       // Same as backend discount factor
    
//     // MCTS statistics tracking
//     nodeStats: new Map(),  // Maps node IDs to {visits: number, totalReward: number}
//     currentNode: null,
//     nodeHistory: [],       // Track path for backpropagation
//     reviewCache: new Map(), // Cache review scores to identify low-scoring aspects
    
//     // Available actions - properly defined set
//     actions: [
//         "review_and_refine",
//         "retrieve_and_refine",
//         "refresh_idea"
//     ],
    
//     // Start automated exploration
//     startExploration: function() {
//         if (this.isRunning) return;
        
//         this.isRunning = true;
//         this.currentIteration = 0;
//         this.nodeStats.clear();
//         this.nodeHistory = [];
//         this.reviewCache.clear();
        
//         // Show starting message in chat
//         this.showSystemMessage("Starting automated idea exploration using MCTS...", true);
        
//         // Start the MCTS exploration loop
//         this.exploreNextStep();
//     },
    
//     // Stop automated exploration
//     stopExploration: function() {
//         this.isRunning = false;
//         this.showSystemMessage("Automated exploration stopped.", false);
//     },
    
//     // Select next action using UCT formula and domain knowledge
//     selectAction: function() {
//         if (!this.currentNode) {
//             // First get review scores to inform decision making
//             return "review_and_refine";
//         }
        
//         const stats = this.nodeStats.get(this.currentNode) || { visits: 0, totalReward: 0 };
//         const parentVisits = stats.visits;
        
//         // Get current review scores if available
//         const reviewData = this.reviewCache.get(this.currentNode);
//         let lowScoringAspects = [];
        
//         if (reviewData) {
//             // Find the three lowest scoring aspects
//             lowScoringAspects = Object.entries(reviewData.scores || {})
//                 .sort(([,a], [,b]) => a - b)
//                 .slice(0, 3)
//                 .map(([aspect]) => aspect);
//         }
        
//         // Calculate UCT scores with domain-specific adjustments
//         const scores = this.actions.map(action => {
//             const childStats = this.nodeStats.get(`${this.currentNode}-${action}`) || 
//                              { visits: 0, totalReward: 0 };
            
//             if (childStats.visits === 0) {
//                 return { action, score: Infinity }; // Unexplored actions have infinite potential
//             }
            
//             // Calculate base UCT score
//             const exploitation = childStats.totalReward / childStats.visits;
//             const exploration = this.explorationConstant * 
//                 Math.sqrt(Math.log(parentVisits) / childStats.visits);
            
//             let score = exploitation + exploration;
            
//             // Apply domain-specific adjustments
//             if (action === "review_and_refine" && lowScoringAspects.length > 0) {
//                 // Increase score if there are clear areas for improvement
//                 score *= 1.2;
//             } else if (action === "retrieve_and_refine" && (!reviewData || reviewData.scores?.novelty < 7)) {
//                 // Prefer knowledge retrieval if novelty score is low or unknown
//                 score *= 1.15;
//             }
            
//             return { action, score };
//         });
        
//         // Select action with highest adjusted UCT score
//         return scores.reduce((best, current) => 
//             current.score > best.score ? current : best
//         ).action;
//     },
    
//     // Execute selected action with proper sequencing
//     executeAction: async function(actionName) {
//         const ideaText = document.getElementById('main-idea').innerText;
        
//         if (actionName === "review_and_refine") {
//             // First get reviews
//             const reviewResponse = await this.getReviews();
//             if (!reviewResponse || !reviewResponse.scores) {
//                 throw new Error("Failed to get reviews");
//             }
            
//             // Cache the review data
//             this.reviewCache.set(this.currentNode, reviewResponse);
            
//             // Find three lowest scoring aspects
//             const lowAspects = Object.entries(reviewResponse.scores)
//                 .sort(([,a], [,b]) => a - b)
//                 .slice(0, 3);
            
//             // Get detailed feedback for these aspects
//             const aspectReviews = await Promise.all(
//                 lowAspects.map(([aspect]) => 
//                     this.getAspectReview(ideaText, aspect)
//                 )
//             );
            
//             // Improve idea based on feedback
//             return await this.improveWithFeedback(ideaText, aspectReviews);
            
//         } else if (actionName === "retrieve_and_refine") {
//             // Generate search query
//             const queryResponse = await $.ajax({
//                 url: "/api/generate_query",
//                 type: "POST",
//                 contentType: "application/json",
//                 data: JSON.stringify({ idea: ideaText })
//             });
            
//             if (!queryResponse.query) {
//                 throw new Error("Failed to generate query");
//             }
            
//             // Retrieve knowledge
//             const retrievalResponse = await $.ajax({
//                 url: "/api/retrieve_knowledge",
//                 type: "POST",
//                 contentType: "application/json",
//                 data: JSON.stringify({ query: queryResponse.query })
//             });
            
//             if (!retrievalResponse.sections) {
//                 throw new Error("Failed to retrieve knowledge");
//             }
            
//             // Improve idea with retrieved knowledge
//             return await $.ajax({
//                 url: "/api/improve_idea_with_knowledge",
//                 type: "POST",
//                 contentType: "application/json",
//                 data: JSON.stringify({ 
//                     idea: ideaText,
//                     knowledge: retrievalResponse.sections
//                 })
//             });
            
//         } else { // refresh_idea
//             return await $.ajax({
//                 url: "/api/refresh_idea",
//                 type: "POST",
//                 contentType: "application/json",
//                 data: JSON.stringify({ idea: ideaText })
//             });
//         }
//     },
    
//     // Helper methods for review and improvement
//     getReviews: function() {
//         return $.ajax({
//             url: "/api/step",
//             type: "POST",
//             contentType: "application/json",
//             data: JSON.stringify({ action: "judge" })
//         });
//     },
    
//     getAspectReview: function(idea, aspect) {
//         return $.ajax({
//             url: "/api/review_aspect",
//             type: "POST",
//             contentType: "application/json",
//             data: JSON.stringify({ idea, aspect })
//         });
//     },
    
//     improveWithFeedback: function(idea, reviews) {
//         return $.ajax({
//             url: "/api/improve_idea",
//             type: "POST",
//             contentType: "application/json",
//             data: JSON.stringify({ 
//                 idea,
//                 accepted_reviews: reviews.map(r => ({
//                     aspect: r.review_data.aspect,
//                     category: r.review_data.category,
//                     review: r.review_data.review
//                 }))
//             })
//         });
//     },
    
//     // Update node statistics for backpropagation
//     updateStats: function(nodeId, reward) {
//         const stats = this.nodeStats.get(nodeId) || { visits: 0, totalReward: 0 };
//         stats.visits += 1;
//         stats.totalReward += reward;
//         this.nodeStats.set(nodeId, stats);
//     },
    
//     // Backpropagate rewards through the node history
//     backpropagate: function(reward) {
//         let currentReward = reward;
//         for (const nodeId of [...this.nodeHistory].reverse()) {
//             this.updateStats(nodeId, currentReward);
//             currentReward *= this.discountFactor; // Apply discount factor like backend
//         }
//     },
    
//     // Explore the next step in the MCTS process
//     exploreNextStep: async function() {
//         if (!this.isRunning || this.currentIteration >= this.maxIterations) {
//             if (this.isRunning) {
//                 this.showSystemMessage(`Automated exploration completed after ${this.currentIteration} iterations.`, false);
//                 this.isRunning = false;
//             }
//             return;
//         }
        
//         // Increment iteration counter
//         this.currentIteration++;
        
//         try {
//             // Selection - Choose next action using UCT
//             const action = this.selectAction();
            
//             // Show the selected action in chat
//             this.showSystemMessage(
//                 `Iteration ${this.currentIteration}/${this.maxIterations}: ` +
//                 `Performing ${action.replace(/_/g, ' ')}...`, 
//                 true
//             );
            
//             // Execute the selected action
//             const response = await this.executeAction(action);
            
//             if (response && response.idea) {
//                 // Track new node
//                 const newNodeId = response.nodeId || `node-${Date.now()}`;
//                 this.currentNode = newNodeId;
//                 this.nodeHistory.push(newNodeId);
                
//                 // Backpropagate reward
//                 const reward = response.average_score ? response.average_score / 10 : 0.5;
//                 this.backpropagate(reward);
                
//                 // Show result
//                 this.showSystemMessage(
//                     `Action complete! Score: ${(reward * 10).toFixed(1)}/10`,
//                     false
//                 );
                
//                 // Schedule next step after delay
//                 setTimeout(() => {
//                     this.exploreNextStep();
//                 }, this.explorationDelay);
//             } else {
//                 throw new Error("Invalid response from action execution");
//             }
            
//         } catch (error) {
//             console.error("Error in MCTS exploration:", error);
//             this.showSystemMessage("Error in exploration process. Stopping automation.", false);
//             this.isRunning = false;
//         }
//     },
    
//     // Display a system message in the chat box
//     showSystemMessage: function(message, isLoading = false) {
//         const chatBox = document.getElementById("chat-box");
//         let messageContainer;
        
//         if (isLoading) {
//             messageContainer = document.createElement("div");
//             messageContainer.setAttribute("data-sender", "system");
//             messageContainer.innerHTML = `
//                 <div class="loading-state">
//                     <div class="spinner"></div>
//                     <div class="loading-text">${message}</div>
//                 </div>
//             `;
//         } else {
//             messageContainer = document.createElement("div");
//             messageContainer.setAttribute("data-sender", "system");
//             messageContainer.textContent = message;
//         }
        
//         chatBox.appendChild(messageContainer);
//         chatBox.scrollTop = chatBox.scrollHeight;
        
//         return messageContainer;
//     },
    
//     // Check if we can start exploration
//     canStartExploration: function() {
//         const mainIdea = document.getElementById('main-idea');
//         return mainIdea && mainIdea.textContent.trim().length > 0;
//     }
// };

// // Toggle the automatic exploration on/off
// function toggleAutoGenerate() {
//     const button = document.querySelector('.auto-generate');
    
//     if (mctsAuto.isRunning) {
//         mctsAuto.stopExploration();
//         button.classList.remove('active');
//         return false;
//     } else {
//         if (!mctsAuto.canStartExploration()) {
//             alert("Please enter a research idea first before starting automated exploration.");
//             return false;
//         }
        
//         // Instead of using the client-side MCTS implementation directly,
//         // we'll use the server's UCT algorithm for action selection
//         // by sending the 'generate' action
//         button.classList.add('active');
        
//         // Show a loading message in the chat
//         const chatArea = $("#chat-box");
//         const loadingMessage = $('<div></div>')
//             .attr('data-sender', 'system')
//             .text('Starting automated exploration...')
//             .hide();
        
//         chatArea.append(loadingMessage);
//         loadingMessage.slideDown();
//         chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
        
//         // Call the backend with the 'generate' action
//         $.ajax({
//             url: '/api/step',
//             type: 'POST',
//             contentType: 'application/json',
//             data: JSON.stringify({ action: 'generate' }),
//             success: function(data) {
//                 // Update the idea in the UI
//                 if (data.idea) {
//                     $("#main-idea").html(formatMessage(data.idea));
//                 }
                
//                 // Update chat with any new messages
//                 if (data.messages) {
//                     updateChat(data.messages);
//                 }
                
//                 if (data.average_score !== undefined) {
//                     updateScoreDisplay(data.average_score);
//                 }
                
//                 // Schedule the next automation step after a delay
//                 setTimeout(() => {
//                     // If still in auto mode, continue with next step
//                     if (button.classList.contains('active')) {
//                         toggleAutoGenerate();
//                     }
//                 }, 5000); // 5 second delay between steps
//             },
//             error: function(xhr, status, error) {
//                 const errorMsg = $('<div></div>')
//                     .attr('data-sender', 'system')
//                     .text('Error: ' + (xhr.responseJSON?.error || error))
//                     .hide();
//                 chatArea.append(errorMsg);
//                 errorMsg.slideDown();
//                 chatArea.animate({ scrollTop: chatArea[0].scrollHeight }, 'slow');
                
//                 // Stop auto-generation on error
//                 button.classList.remove('active');
//             }
//         });
        
//         return true;
//     }
// }

// MCTS Automated Exploration Module for IRIS with Memory-Aware Selection
// This module implements automated idea exploration using backend UCT algorithm

// Import utility functions if they don't exist in the global scope
if (typeof formatMessage !== 'function') {
    function formatMessage(content) {
        if (!content) return '';
        // Ensure markdown rendering if marked library is available
        if (typeof marked !== 'undefined') {
            return marked.parse(content);
        }
        return content;
    }
}

if (typeof updateChat !== 'function') {
    function updateChat(messages) {
        if (!messages || !messages.length) return;
        
        const chatBox = $("#chat-box");
        // Append new messages
        messages.forEach(msg => {
            if (msg.role && msg.content) {
                const messageDiv = $('<div></div>')
                    .attr('data-sender', msg.role)
                    .html(formatMessage(msg.content));
                chatBox.append(messageDiv);
            }
        });
        
        // Scroll to bottom
        chatBox.scrollTop(chatBox[0].scrollHeight);
    }
}

if (typeof updateScoreDisplay !== 'function') {
    function updateScoreDisplay(score) {
        if (!score && score !== 0) return;
        
        // Find or create the score display element
        let scoreElement = $(".score-display");
        if (scoreElement.length === 0) {
            scoreElement = $('<div class="score-display"></div>');
            $("#main-idea-container").prepend(scoreElement);
        }
        
        // Update the score with 2 decimal places
        const scoreValue = parseFloat(score).toFixed(2);
        scoreElement.html(`<span class="score-label">Score:</span> <span class="score-value">${scoreValue}</span>`);
        
        // Apply color based on score
        if (scoreValue >= 8.0) {
            scoreElement.removeClass().addClass('score-display high-score');
        } else if (scoreValue >= 6.0) {
            scoreElement.removeClass().addClass('score-display medium-score');
        } else {
            scoreElement.removeClass().addClass('score-display low-score');
        }
    }
}

const mctsAuto = {
    // Configuration
    isRunning: false,
    maxIterations: 10,  // Increased for better exploration
    currentIteration: 0,
    explorationDelay: 6000,  // 6 seconds to allow backend processing
    
    // Memory tracking for visualization
    memoryStats: {
        actionHistory: [],
        scoreHistory: [],
        performanceTrend: 'stable',
        lastMemoryUpdate: null
    },
    
    // FIXED: Only include actions that should be automated (removed "judge")
    // These match the valid_actions in backend step() function
    validActions: [
        "review_and_refine",
        "retrieve_and_refine", 
        "refresh_idea"
    ],
    
    // Start automated exploration using backend UCT
    startExploration: function() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.currentIteration = 0;
        this.memoryStats.actionHistory = [];
        this.memoryStats.scoreHistory = [];
        
        // Add memory panel
        this.addMemoryPanel();
        
        // Show starting message in chat
        this.showSystemMessage("🧠 Starting memory-aware MCTS exploration...", true);
        
        // Start the exploration loop
        this.exploreNextStep();
    },
    
    // Stop automated exploration
    stopExploration: function() {
        this.isRunning = false;
        this.hideMemoryPanel();
        this.showSystemMessage("Automated exploration stopped.", false);
    },
    
    // FIXED: Use backend UCT selection instead of client-side selection
    exploreNextStep: async function() {
        if (!this.isRunning || this.currentIteration >= this.maxIterations) {
            if (this.isRunning) {
                this.showSystemMessage(`Memory-aware exploration completed after ${this.currentIteration} iterations.`, false);
                this.isRunning = false;
                this.hideMemoryPanel();
            }
            return;
        }
        
        // Increment iteration counter
        this.currentIteration++;
        
        try {
            // Show iteration info
            this.showSystemMessage(
                `🔄 Iteration ${this.currentIteration}/${this.maxIterations}: Using backend UCT selection...`,
                true
            );
            
            // FIXED: Let backend select action using memory-aware UCT
            const response = await $.ajax({
                url: '/api/step',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ 
                    action: 'generate',
                    use_memory: true  // Enable memory-aware selection
                })
            });
            
            // Process the response
            if (response) {
                // Update memory stats
                this.updateMemoryStats(response);
                
                // Update UI
                if (response.idea) {
                    $("#main-idea").html(formatMessage(response.idea));
                    window.main_idea = response.idea; // Update global variable
                }
                
                // Update chat with backend messages
                if (response.messages && Array.isArray(response.messages)) {
                    response.messages.forEach(msg => {
                        if (msg.role === 'system') {
                            this.showSystemMessage(msg.content, false);
                        }
                    });
                }
                
                if (response.average_score !== undefined) {
                    updateScoreDisplay(response.average_score);
                    this.memoryStats.scoreHistory.push(response.average_score);
                }
                
                // Update memory visualization
                this.updateMemoryVisualization();
                
                // Show completion message for this step
                const score = response.average_score || 0;
                this.showSystemMessage(
                    `✅ Step complete! Current score: ${score.toFixed(1)}/10`,
                    false
                );
                
                // Schedule next step
                setTimeout(() => {
                    this.exploreNextStep();
                }, this.explorationDelay);
                
            } else {
                throw new Error("Invalid response from backend");
            }
            
        } catch (error) {
            console.error("Error in MCTS exploration:", error);
            this.showSystemMessage(`❌ Error: ${error.message || 'Unknown error'}`, false);
            this.isRunning = false;
            this.hideMemoryPanel();
        }
    },
    
    // Update memory statistics from backend response
    updateMemoryStats: function(response) {
        // Extract action from system messages
        if (response.messages && Array.isArray(response.messages)) {
            response.messages.forEach(msg => {
                if (msg.role === 'system' && msg.content.includes('selection:')) {
                    // Extract action from memory-guided selection message
                    const actionMatch = msg.content.match(/selection: (\w+(?:_\w+)*)/);
                    if (actionMatch) {
                        this.memoryStats.actionHistory.push(actionMatch[1]);
                    }
                }
            });
        }
        
        // Update performance trend
        if (this.memoryStats.scoreHistory.length >= 3) {
            const recent = this.memoryStats.scoreHistory.slice(-3);
            const trend = recent[recent.length - 1] - recent[0];
            
            if (trend > 0.5) {
                this.memoryStats.performanceTrend = 'improving';
            } else if (trend < -0.5) {
                this.memoryStats.performanceTrend = 'declining';
            } else {
                this.memoryStats.performanceTrend = 'stable';
            }
        }
        
        this.memoryStats.lastMemoryUpdate = new Date().toISOString();
    },
    
    // Add memory visualization panel
    addMemoryPanel: function() {
        if ($("#memory-panel").length > 0) return; // Already exists
        
        const memoryPanel = $(`
            <div id="memory-panel" class="memory-panel">
                <div class="memory-header">
                    <h3>🧠 Memory & MCTS Progress</h3>
                    <button class="memory-close" onclick="mctsAuto.hideMemoryPanel()">×</button>
                </div>
                <div class="memory-content">
                    <div class="memory-stats">
                        <div class="stat">
                            <label>Iteration:</label>
                            <span id="current-iteration">0 / ${this.maxIterations}</span>
                        </div>
                        <div class="stat">
                            <label>Actions Taken:</label>
                            <span id="actions-count">0</span>
                        </div>
                        <div class="stat">
                            <label>Performance:</label>
                            <span id="performance-trend" class="trend-stable">stable</span>
                        </div>
                    </div>
                    
                    <div class="action-distribution">
                        <h4>Action Usage</h4>
                        <div id="action-chart"></div>
                    </div>
                    
                    <div class="score-trend">
                        <h4>Score Progression</h4>
                        <canvas id="score-chart" width="260" height="80"></canvas>
                    </div>
                </div>
            </div>
        `);
        
        $("body").append(memoryPanel);
        memoryPanel.hide().slideDown();
    },
    
    // Hide memory panel
    hideMemoryPanel: function() {
        $("#memory-panel").slideUp(function() {
            $(this).remove();
        });
    },
    
    // Update memory visualization
    updateMemoryVisualization: function() {
        if ($("#memory-panel").length === 0) return;
        
        // Update iteration counter
        $("#current-iteration").text(`${this.currentIteration} / ${this.maxIterations}`);
        
        // Update actions count
        $("#actions-count").text(this.memoryStats.actionHistory.length);
        
        // Update performance trend
        const trendElement = $("#performance-trend");
        const trend = this.memoryStats.performanceTrend;
        trendElement.text(trend).removeClass().addClass(`trend-${trend}`);
        
        // Update action distribution chart
        this.updateActionChart();
        
        // Update score chart
        this.updateScoreChart();
    },
    
    // Update action distribution visualization
    updateActionChart: function() {
        const chartContainer = $("#action-chart");
        chartContainer.empty();
        
        // Count action occurrences
        const actionCounts = {};
        this.memoryStats.actionHistory.forEach(action => {
            actionCounts[action] = (actionCounts[action] || 0) + 1;
        });
        
        const total = this.memoryStats.actionHistory.length;
        
        Object.entries(actionCounts).forEach(([action, count]) => {
            const percentage = total > 0 ? Math.round((count / total) * 100) : 0;
            const actionBar = $(`
                <div class="action-bar-item">
                    <span class="action-name">${action.replace(/_/g, ' ')}</span>
                    <div class="action-bar-container">
                        <div class="action-bar" style="width: ${percentage}%"></div>
                    </div>
                    <span class="action-count">${count}</span>
                </div>
            `);
            chartContainer.append(actionBar);
        });
    },
    
    // Update score progression chart
    updateScoreChart: function() {
        const canvas = document.getElementById('score-chart');
        if (!canvas || this.memoryStats.scoreHistory.length < 2) return;
        
        const ctx = canvas.getContext('2d');
        const scores = this.memoryStats.scoreHistory;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw grid lines
        ctx.strokeStyle = '#e9ecef';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 10; i++) {
            const y = (i / 10) * canvas.height;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
        
        // Draw score line
        ctx.strokeStyle = this.memoryStats.performanceTrend === 'improving' ? '#28a745' : 
                         this.memoryStats.performanceTrend === 'declining' ? '#dc3545' : '#007bff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let i = 0; i < scores.length; i++) {
            const x = (i / (scores.length - 1)) * canvas.width;
            const y = canvas.height - (scores[i] / 10) * canvas.height;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.stroke();
        
        // Draw points
        ctx.fillStyle = ctx.strokeStyle;
        for (let i = 0; i < scores.length; i++) {
            const x = (i / (scores.length - 1)) * canvas.width;
            const y = canvas.height - (scores[i] / 10) * canvas.height;
            
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, 2 * Math.PI);
            ctx.fill();
        }
    },
    
    // Display a system message in the chat box
    showSystemMessage: function(message, isLoading = false) {
        const chatBox = $("#chat-box");
        let messageContainer;
        
        if (isLoading) {
            messageContainer = $('<div></div>')
                .attr('data-sender', 'system')
                .addClass('mcts-loading')
                .html(`
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <div class="loading-text">${message}</div>
                    </div>
                `);
        } else {
            messageContainer = $('<div></div>')
                .attr('data-sender', 'system')
                .addClass('mcts-message')
                .text(message);
        }
        
        chatBox.append(messageContainer);
        messageContainer.slideDown();
        chatBox.animate({ scrollTop: chatBox[0].scrollHeight }, 'slow');
        
        return messageContainer;
    },
    
    // Check if we can start exploration
    canStartExploration: function() {
        const mainIdea = document.getElementById('main-idea');
        return mainIdea && mainIdea.textContent.trim().length > 0;
    }
};

// FIXED: Main toggle function - use backend UCT instead of client-side selection
function toggleAutoGenerate() {
    const button = document.querySelector('.auto-generate');
    
    if (mctsAuto.isRunning) {
        mctsAuto.stopExploration();
        button.classList.remove('active');
        return false;
    } else {
        if (!mctsAuto.canStartExploration()) {
            alert("Please enter a research idea first before starting automated exploration.");
            return false;
        }
        
        // Start the memory-aware MCTS exploration
        button.classList.add('active');
        mctsAuto.startExploration();
        
        return true;
    }
}

// Export for global use
window.mctsAuto = mctsAuto;
window.toggleAutoGenerate = toggleAutoGenerate;