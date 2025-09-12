# Web Layer and UI Design

## Overview

The web layer uses Litestar with HTMX for a modern, reactive user interface without complex JavaScript. All interactions are server-side rendered with partial page updates for a smooth user experience.

## HTMX Architecture

### Template Structure
```
app/server/templates/
├── base.html                      # Base template with HTMX setup
├── coffee_chat.html               # Main chat interface
├── partials/                      # HTMX partial templates
│   ├── chat_response.html         # Agent response partial
│   ├── streaming_response.html    # Real-time streaming
│   ├── _vector_results.html       # Product search results
│   ├── _vector_error.html         # Error handling
│   ├── _typing_indicator.html     # AI thinking indicator
│   └── _metric_cards.html         # Performance metrics
└── components/                    # Reusable components
    ├── chat_input.html            # Chat input form
    ├── product_card.html          # Product display
    └── session_info.html          # Session metadata
```

### Base Template
```html
<!-- app/server/templates/base.html -->
<!DOCTYPE html>
<html class="h-full" lang="en">
<head>
    <meta charset="utf-8">
    <title>{% block title %}Cymbal Coffee{% endblock %}</title>
    <meta name="referrer" content="same-origin">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    
    <!-- Favicons -->
    <link rel="apple-touch-icon" sizes="180x180" href="{{ url_for('static', file_path='apple-touch-icon.png') }}">
    <link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', file_path='favicon-32x32.png') }}">
    <link rel="icon" type="image/x-icon" href="{{ url_for('static', file_path='favicon.ico') }}">
    
    <!-- HTMX Core -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/htmx.org/dist/ext/sse.js"></script>
    
    <!-- Styles -->
    <link rel="stylesheet" href="{{ url_for('static', file_path='css/cymbal-theme.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', file_path='css/chat-interface.css') }}">
    
    <!-- Security Headers -->
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com;">
    
    {% block extra_head %}{% endblock %}
</head>

<body class="h-full bg-coffee-cream">
    <!-- Header -->
    <header class="bg-coffee-dark text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center py-6">
                <div class="flex items-center">
                    <img class="h-8 w-auto" src="{{ url_for('static', file_path='cymbal-logo.svg') }}" alt="Cymbal Coffee">
                    <h1 class="ml-3 text-2xl font-bold">Cymbal Coffee</h1>
                </div>
                <nav class="hidden md:flex space-x-8">
                    <a href="/" class="text-coffee-light hover:text-white transition-colors">Chat</a>
                    <a href="/menu" class="text-coffee-light hover:text-white transition-colors">Menu</a>
                </nav>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 overflow-hidden">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="bg-coffee-medium text-white py-8">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="text-center">
                <p>&copy; 2024 Cymbal Coffee. Powered by AI and passion for great coffee.</p>
            </div>
        </div>
    </footer>

    <!-- HTMX Configuration -->
    <script>
        // Configure HTMX
        htmx.config.responseHandling.swapOnError = false;
        htmx.config.defaultSwapStyle = 'innerHTML';
        htmx.config.scrollIntoViewOnBoost = false;
        
        // Global error handling
        document.body.addEventListener('htmx:responseError', function(event) {
            console.error('HTMX Error:', event.detail);
            // Show user-friendly error message
        });
        
        // Loading indicators
        document.body.addEventListener('htmx:beforeRequest', function(event) {
            const indicator = event.target.closest('[data-loading-indicator]');
            if (indicator) {
                indicator.classList.add('loading');
            }
        });
        
        document.body.addEventListener('htmx:afterRequest', function(event) {
            const indicator = event.target.closest('[data-loading-indicator]');
            if (indicator) {
                indicator.classList.remove('loading');
            }
        });
    </script>

    {% block extra_scripts %}{% endblock %}
</body>
</html>
```

### Main Chat Interface
```html
<!-- app/server/templates/coffee_chat.html -->
{% extends "base.html" %}

{% block title %}Chat with AI Barista - Cymbal Coffee{% endblock %}

{% block content %}
<div class="h-full flex flex-col max-w-4xl mx-auto p-4">
    <!-- Chat Header -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-4">
        <div class="flex justify-between items-center">
            <div>
                <h2 class="text-2xl font-bold text-coffee-dark">Chat with our AI Barista</h2>
                <p class="text-coffee-medium">Ask about our coffee, get recommendations, or just chat about coffee!</p>
            </div>
            <div class="text-right">
                <div class="text-sm text-coffee-light">Session: {{ session.id[:8] if session else 'new' }}</div>
                <div class="text-sm text-coffee-light">{{ conversation_count or 0 }} messages</div>
            </div>
        </div>
    </div>

    <!-- Chat Messages Container -->
    <div class="flex-1 bg-white rounded-lg shadow-sm overflow-hidden flex flex-col">
        <!-- Messages Area -->
        <div id="chat-messages" 
             class="flex-1 overflow-y-auto p-6 space-y-4"
             data-loading-indicator>
            
            <!-- Welcome Message -->
            {% if not conversation_history %}
            <div class="flex items-start space-x-3">
                <div class="flex-shrink-0">
                    <div class="w-8 h-8 bg-coffee-medium rounded-full flex items-center justify-center">
                        <span class="text-white text-sm font-semibold">AI</span>
                    </div>
                </div>
                <div class="flex-1">
                    <div class="bg-coffee-light text-white rounded-lg px-4 py-2">
                        <p>Hello! I'm your AI coffee assistant. I can help you find the perfect coffee, answer questions about our products, or just chat about coffee. What can I help you with today?</p>
                    </div>
                </div>
            </div>
            {% endif %}

            <!-- Existing Conversation History -->
            {% for message in conversation_history %}
                {% if message.role == 'user' %}
                    {% include 'partials/_user_message.html' %}
                {% elif message.role == 'assistant' %}
                    {% include 'partials/_assistant_message.html' %}
                {% endif %}
            {% endfor %}
        </div>

        <!-- Chat Input Area -->
        <div class="border-t border-coffee-cream p-4">
            {% include 'components/chat_input.html' %}
        </div>
    </div>
</div>

<!-- Typing Indicator (Hidden by default) -->
<template id="typing-indicator-template">
    <div class="flex items-start space-x-3 typing-indicator">
        <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-coffee-medium rounded-full flex items-center justify-center">
                <span class="text-white text-sm font-semibold">AI</span>
            </div>
        </div>
        <div class="flex-1">
            <div class="bg-gray-100 rounded-lg px-4 py-2">
                <div class="flex space-x-1">
                    <div class="w-2 h-2 bg-coffee-medium rounded-full animate-bounce"></div>
                    <div class="w-2 h-2 bg-coffee-medium rounded-full animate-bounce" style="animation-delay: 0.1s;"></div>
                    <div class="w-2 h-2 bg-coffee-medium rounded-full animate-bounce" style="animation-delay: 0.2s;"></div>
                </div>
            </div>
        </div>
    </div>
</template>
{% endblock %}

{% block extra_scripts %}
<script>
    // Auto-scroll to bottom on new messages
    function scrollToBottom() {
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Handle form submission
    document.addEventListener('htmx:afterRequest', function(event) {
        if (event.target.matches('#chat-form')) {
            scrollToBottom();
        }
    });

    // Show typing indicator
    document.addEventListener('htmx:beforeRequest', function(event) {
        if (event.target.matches('#chat-form')) {
            const template = document.getElementById('typing-indicator-template');
            const indicator = template.content.cloneNode(true);
            document.getElementById('chat-messages').appendChild(indicator);
            scrollToBottom();
        }
    });

    // Remove typing indicator
    document.addEventListener('htmx:afterRequest', function(event) {
        if (event.target.matches('#chat-form')) {
            const typingIndicator = document.querySelector('.typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
        }
    });
</script>
{% endblock %}
```

### Chat Input Component
```html
<!-- app/server/templates/components/chat_input.html -->
<form id="chat-form"
      hx-post="/chat"
      hx-target="#chat-messages"
      hx-swap="beforeend"
      hx-indicator="#chat-form [data-loading]"
      class="flex space-x-3">
    
    <!-- Hidden session ID -->
    <input type="hidden" name="session_id" value="{{ session.id if session else '' }}">
    
    <!-- Message Input -->
    <div class="flex-1">
        <input type="text"
               name="message"
               id="message-input"
               placeholder="Ask about our coffee, get recommendations..."
               required
               maxlength="500"
               autocomplete="off"
               class="w-full px-4 py-2 border border-coffee-light rounded-lg focus:outline-none focus:ring-2 focus:ring-coffee-medium focus:border-transparent">
    </div>
    
    <!-- Send Button -->
    <button type="submit"
            class="bg-coffee-medium hover:bg-coffee-dark text-white px-6 py-2 rounded-lg transition-colors flex items-center space-x-2 disabled:opacity-50"
            data-loading>
        <span class="default-text">Send</span>
        <span class="loading-text hidden">
            <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
        </span>
    </button>
</form>

<script>
    // Clear input on successful submission
    document.getElementById('chat-form').addEventListener('htmx:afterRequest', function(event) {
        if (event.detail.successful) {
            document.getElementById('message-input').value = '';
        }
    });

    // Focus input on page load
    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('message-input').focus();
    });

    // Submit on Enter
    document.getElementById('message-input').addEventListener('keypress', function(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            document.getElementById('chat-form').dispatchEvent(new Event('submit'));
        }
    });
</script>
```

### Chat Response Partial
```html
<!-- app/server/templates/partials/chat_response.html -->
<!-- User Message -->
<div class="flex items-start space-x-3 justify-end">
    <div class="flex-1 text-right">
        <div class="bg-coffee-medium text-white rounded-lg px-4 py-2 inline-block max-w-xs lg:max-w-md">
            <p>{{ user_message }}</p>
        </div>
        <div class="text-xs text-coffee-light mt-1">Just now</div>
    </div>
    <div class="flex-shrink-0">
        <div class="w-8 h-8 bg-coffee-dark rounded-full flex items-center justify-center">
            <span class="text-white text-sm font-semibold">You</span>
        </div>
    </div>
</div>

<!-- AI Response -->
<div class="flex items-start space-x-3">
    <div class="flex-shrink-0">
        <div class="w-8 h-8 bg-coffee-medium rounded-full flex items-center justify-center">
            <span class="text-white text-sm font-semibold">AI</span>
        </div>
    </div>
    <div class="flex-1">
        <div class="bg-coffee-light text-white rounded-lg px-4 py-2">
            <!-- Agent Response -->
            <div class="prose prose-sm text-white max-w-none">
                {{ ai_response | markdown }}
            </div>
            
            <!-- Product Results (if any) -->
            {% if products %}
                <div class="mt-3 space-y-2">
                    {% for product in products %}
                        {% include 'components/product_card.html' %}
                    {% endfor %}
                </div>
            {% endif %}
        </div>
        
        <!-- Metadata -->
        <div class="text-xs text-coffee-light mt-1 flex items-center space-x-2">
            <span>{{ agent_used }}</span>
            {% if from_cache %}
                <span class="bg-green-100 text-green-800 px-2 py-1 rounded">Cached</span>
            {% endif %}
            {% if similarity_score %}
                <span>Confidence: {{ "%.0f" | format(similarity_score * 100) }}%</span>
            {% endif %}
            <span>{{ response_time_ms | round }}ms</span>
        </div>
    </div>
</div>
```

### Product Card Component
```html
<!-- app/server/templates/components/product_card.html -->
<div class="bg-white text-coffee-dark rounded-lg p-3 border border-coffee-cream">
    <div class="flex items-start space-x-3">
        <div class="flex-1">
            <h4 class="font-semibold text-coffee-dark">{{ product.name }}</h4>
            <p class="text-sm text-coffee-medium mt-1">{{ product.description[:100] }}...</p>
            
            <!-- Product Metadata -->
            {% if product.metadata %}
                <div class="mt-2 flex flex-wrap gap-1">
                    {% if product.metadata.origin %}
                        <span class="bg-coffee-cream text-coffee-dark px-2 py-1 text-xs rounded">{{ product.metadata.origin }}</span>
                    {% endif %}
                    {% if product.metadata.roast_level %}
                        <span class="bg-coffee-cream text-coffee-dark px-2 py-1 text-xs rounded">{{ product.metadata.roast_level }} Roast</span>
                    {% endif %}
                </div>
            {% endif %}
        </div>
        
        <!-- Price -->
        <div class="text-right">
            <div class="text-lg font-bold text-coffee-dark">${{ product.price }}</div>
            {% if product.similarity_score %}
                <div class="text-xs text-coffee-light">{{ "%.0f" | format(product.similarity_score * 100) }}% match</div>
            {% endif %}
        </div>
    </div>
</div>
```

## Litestar Controllers

### Main Chat Controller
```python
# app/server/controllers.py
from __future__ import annotations

import secrets
from typing import Annotated

from litestar import Controller, get, post
from litestar.di import Provide
from litestar.plugins.htmx import HTMXRequest, HTMXTemplate
from litestar.response import Template

from app import schemas as s
from app.server import deps
from app.services import AgentService, ChatService


class CoffeeChatController(Controller):
    """Coffee chat controller with HTMX support."""
    
    dependencies = {
        "agent_service": Provide(deps.provide_agent_service),
        "chat_service": Provide(deps.provide_chat_service),
    }

    @get(path="/", name="coffee_chat.index")
    async def show_coffee_chat(
        self,
        chat_service: ChatService,
        user_id: str = "default"
    ) -> Template:
        """Show main chat interface."""
        
        # Get active session and conversation history
        session = await chat_service.get_active_session(user_id)
        conversation_history = []
        conversation_count = 0
        
        if session:
            conversation_history = await chat_service.get_conversation_history(
                session.id, limit=20
            )
            conversation_count = len(conversation_history)
        
        return Template(
            template_name="coffee_chat.html",
            context={
                "session": session,
                "conversation_history": conversation_history,
                "conversation_count": conversation_count,
                "csp_nonce": self._generate_csp_nonce(),
            },
        )

    @post(path="/chat", name="coffee_chat.message")
    async def handle_chat_message(
        self,
        data: s.ChatMessage,
        agent_service: AgentService,
        request: HTMXRequest,
    ) -> HTMXTemplate:
        """Handle chat message with HTMX response."""
        
        # Process through agent system
        response = await agent_service.process_query(
            query=data.message,
            user_id=data.user_id or "default",
            session_id=data.session_id,
            use_cache=True
        )
        
        # Extract products from response if any
        products = []
        if hasattr(response, 'products_found') and response.products_found:
            products = response.products_found

        # Return HTMX partial
        return HTMXTemplate(
            template_name="partials/chat_response.html",
            context={
                "user_message": data.message,
                "ai_response": response.content,
                "agent_used": response.agent_used,
                "from_cache": response.from_cache,
                "similarity_score": getattr(response, 'similarity_score', None),
                "response_time_ms": response.processing_time,
                "products": products,
                "query_id": response.query_id,
            },
        )

    @get(path="/stream/{query_id:str}", name="coffee_chat.stream")
    async def stream_response(
        self,
        query_id: str,
        agent_service: AgentService,
    ) -> str:
        """Stream real-time agent response (SSE)."""
        
        async def generate():
            async for chunk in agent_service.stream_response(query_id):
                yield f"data: {chunk}\n\n"
        
        return Response(
            content=generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    @staticmethod
    def _generate_csp_nonce() -> str:
        """Generate CSP nonce for security."""
        return secrets.token_urlsafe(16)
```

### API Controller
```python
# app/server/api_controllers.py
from typing import Annotated

from litestar import Controller, get, post
from litestar.di import Provide

from app import schemas as s
from app.server import deps
from app.services import AgentService, ProductService, MetricsService


class APIController(Controller):
    """REST API controller for programmatic access."""
    
    path = "/api/v1"
    
    dependencies = {
        "agent_service": Provide(deps.provide_agent_service),
        "product_service": Provide(deps.provide_product_service),
        "metrics_service": Provide(deps.provide_metrics_service),
    }

    @post("/chat", name="api.chat")
    async def chat_api(
        self,
        data: s.ChatMessage,
        agent_service: AgentService,
    ) -> s.AgentResponse:
        """REST API endpoint for chat."""
        return await agent_service.process_query(
            query=data.message,
            user_id=data.user_id or "default",
            session_id=data.session_id
        )

    @get("/products/search", name="api.products.search")
    async def search_products(
        self,
        q: str,
        limit: int = 10,
        product_service: ProductService,
    ) -> list[s.Product]:
        """Search products API."""
        return await product_service.search_by_text(q, limit)

    @get("/metrics/stats", name="api.metrics.stats")
    async def get_stats(
        self,
        hours: int = 24,
        metrics_service: MetricsService,
    ) -> s.PerformanceStats:
        """Get performance statistics."""
        return await metrics_service.get_performance_stats(hours)
```

## Static Assets

### CSS Theme
```css
/* app/server/static/css/cymbal-theme.css */
:root {
    --coffee-dark: #2D1810;
    --coffee-medium: #6B4423;
    --coffee-light: #A67C52;
    --coffee-cream: #F5F1EB;
    --coffee-accent: #D4AF37;
}

/* Base styles */
body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    line-height: 1.6;
    color: var(--coffee-dark);
}

/* Chat Interface */
.chat-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.messages-area {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    background: linear-gradient(to bottom, #ffffff, var(--coffee-cream));
}

/* Loading states */
.loading .default-text { display: none; }
.loading .loading-text { display: inline-flex; }

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.message-enter {
    animation: fadeIn 0.3s ease-out;
}

/* Responsive design */
@media (max-width: 768px) {
    .chat-container {
        padding: 0.5rem;
    }
    
    .message {
        max-width: 90%;
    }
}
```

## Security Considerations

### CSP Headers
```python
# Security headers in base template
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY", 
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com;"
    )
}
```

### Input Validation
```python
# Input sanitization
def sanitize_message(message: str) -> str:
    """Sanitize user message input."""
    # Remove HTML tags
    message = re.sub(r"<[^>]+>", "", message)
    
    # Limit length
    if len(message) > 500:
        message = message[:500]
        
    # Remove null bytes
    message = message.replace("\x00", "").strip()
    
    return message
```

This web layer provides:
- **Modern UX** with HTMX partial updates
- **Real-time interaction** without JavaScript complexity
- **Mobile-responsive** design
- **Security-first** approach with CSP and input validation
- **Performance optimization** with proper caching
- **Accessibility** with semantic HTML and ARIA labels