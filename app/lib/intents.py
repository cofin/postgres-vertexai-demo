"""Intent classification constants and exemplar data."""

from __future__ import annotations

# Intent exemplars for training the classification model
INTENT_EXEMPLARS = {
    "PRODUCT_SEARCH": [
        "What coffee do you have?",
        "Show me your espresso options",
        "I'm looking for a dark roast",
        "Do you have any lattes?",
        "What drinks are available?",
        "Recommend a coffee",
        "What's your strongest coffee?",
        "I need something with caffeine",
        "Show me your menu",
        "What beverages do you sell?",
        "I want a coffee recommendation",
        "What types of coffee do you serve?",
        "Do you have decaf options?",
        "Show me your specialty drinks",
        "I'm looking for something smooth",
        "What's your most popular drink?",
        "I want something energizing",
        "Do you have cold brew?",
        "Show me your hot beverages",
        "What coffee blends do you offer?",
    ],
    "PRICE_INQUIRY": [
        "How much does it cost?",
        "What's the price?",
        "Is it expensive?",
        "What's your cheapest option?",
        "Show me drinks under $5",
        "How much for a latte?",
        "What are your prices?",
        "Is there anything affordable?",
        "What's the cost of espresso?",
        "Do you have any deals?",
        "What's your price range?",
        "How much is a cappuccino?",
        "Are there any discounts?",
        "What's the cheapest coffee?",
        "How much do you charge?",
        "What's the price list?",
        "Is it budget-friendly?",
        "How much for a small coffee?",
        "What's the pricing?",
        "Any cheap options?",
    ],
    "BREWING_HELP": [
        "How do I make espresso?",
        "What's the best brewing method?",
        "How much coffee should I use?",
        "What temperature for brewing?",
        "How to brew the perfect cup?",
        "What's the ideal grind size?",
        "How long should I brew?",
        "What's the coffee to water ratio?",
        "How do I make a latte at home?",
        "What equipment do I need?",
        "How to froth milk properly?",
        "What's the best water temperature?",
        "How to extract espresso properly?",
        "What's the steeping time?",
        "How do I make cold brew?",
        "What grinder should I use?",
        "How to achieve the perfect crema?",
        "What's the proper tamping technique?",
        "How to calibrate my machine?",
        "Tips for better coffee extraction?",
    ],
    "GENERAL_CONVERSATION": [
        "Hello",
        "Hi there",
        "Good morning",
        "Thank you",
        "Thanks",
        "Goodbye",
        "Bye",
        "See you later",
        "How are you?",
        "Nice to meet you",
        "Tell me about coffee",
        "What's your story?",
        "How's your day?",
        "That's interesting",
        "I appreciate your help",
        "You're welcome",
        "No problem",
        "Have a great day",
        "Take care",
        "Thanks for the help",
        "What's new?",
        "How's business?",
        "That sounds good",
        "I understand",
        "Makes sense",
    ],
    "STORE_INFO": [
        "What are your hours?",
        "When are you open?",
        "Where are you located?",
        "What's your address?",
        "Do you deliver?",
        "Can I order online?",
        "Do you have WiFi?",
        "Is parking available?",
        "What's your phone number?",
        "Do you cater events?",
        "Are you hiring?",
        "What's your website?",
        "Do you have outdoor seating?",
        "Can I make reservations?",
        "What's your capacity?",
        "Are you pet-friendly?",
        "Do you accept cards?",
        "What payment methods?",
        "Is there a drive-through?",
        "How busy are you now?",
    ],
}

# Confidence thresholds for each intent
# Lower threshold = more inclusive, higher threshold = more strict
INTENT_THRESHOLDS = {
    "PRODUCT_SEARCH": 0.75,     # High threshold for product queries
    "PRICE_INQUIRY": 0.70,      # Medium-high for price questions
    "BREWING_HELP": 0.72,       # High for technical questions
    "GENERAL_CONVERSATION": 0.65,  # Lower for casual conversation
    "STORE_INFO": 0.73,         # High for specific info requests
}

# Vector search configuration
VECTOR_SEARCH_CONFIG = {
    # Minimum similarity threshold for any match
    "min_similarity_threshold": 0.6,

    # Maximum number of results to consider
    "max_results": 10,

    # Use approximate search (IVFFlat) for performance
    "use_approximate_search": True,

    # IVFFlat configuration
    "ivfflat_lists": 100,  # Number of lists for IVFFlat index

    # Cache configuration
    "enable_memory_cache": True,
    "memory_cache_size": 1000,  # Max items in memory cache

    # Performance monitoring
    "log_search_times": True,
    "slow_query_threshold_ms": 100,
}

# Intent routing rules
INTENT_ROUTING_RULES = {
    # Fallback intent when no good match is found
    "fallback_intent": "GENERAL_CONVERSATION",

    # Whether to log all classification results
    "log_all_classifications": False,

    # Whether to increment usage counts
    "track_usage_stats": True,

    # Whether to store classifications in chat conversations
    "store_classifications": True,
}

# Intent descriptions for documentation and UI
INTENT_DESCRIPTIONS = {
    "PRODUCT_SEARCH": "User is looking for products or asking about available items",
    "PRICE_INQUIRY": "User is asking about pricing, costs, or budget-related questions",
    "BREWING_HELP": "User needs help with brewing techniques, equipment, or coffee preparation",
    "GENERAL_CONVERSATION": "General conversational messages, greetings, or casual chat",
    "STORE_INFO": "User is asking about store information, hours, location, or services",
}

# Training configuration
TRAINING_CONFIG = {
    # Whether to automatically retrain when new exemplars are added
    "auto_retrain": True,

    # Minimum number of exemplars per intent
    "min_exemplars_per_intent": 10,

    # Maximum number of exemplars per intent (to prevent bloat)
    "max_exemplars_per_intent": 100,

    # Whether to validate exemplar quality during training
    "validate_exemplars": True,

    # Minimum similarity between exemplars in the same intent
    "min_intra_intent_similarity": 0.3,
}

# Export commonly used configurations
__all__ = [
    "INTENT_DESCRIPTIONS",
    "INTENT_EXEMPLARS",
    "INTENT_ROUTING_RULES",
    "INTENT_THRESHOLDS",
    "TRAINING_CONFIG",
    "VECTOR_SEARCH_CONFIG",
]
