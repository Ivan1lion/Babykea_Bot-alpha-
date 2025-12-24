QUIZ_CONFIG = {
    "start": {
        "level": 1,
        "photo": "photo_1",
        "text": "Выберите верное утверждение:",
        "options": {
            "pregnant": {
                "button": "🤰 Я в положении",
                "preview": {
                    "photo": "photo_2",
                    "text": "Коляски для новорожденных..."
                },
                "branch": "pregnant",
                "save": {
                    "user_type": "group_1"
                }
            },
            "stroller_6_plus": {
                "button": "👶 Прогулочная коляска 6+",
                "preview": {
                    "photo": "photo_3",
                    "text": "Коляски для детей от 6 мес..."
                },
                "branch": "stroller_6_plus",
                "save": {
                    "user_type": "group_2"
                }
            },
            "service_only": {
                "button": "🛠 Коляска уже есть",
                "preview": {
                    "photo": "photo_4",
                    "text": "Обслуживание колясок..."
                },
                "branch": "service_only",
                "save": {
                    "user_type": "group_2"
                }
            },
        },
        "next_level": 2
    },

    "pregnant": {
        2: {
            "photo": "photo_5",
            "text": "Сфера применения коляски",
            "options": {
                "daily": {
                    "button": "Для ежедневных прогулок",
                    "preview": {
                        "photo": "photo_6",
                        "text": "Для ежедневных прогулок"
                    },
                    "save": {
                        "usage": "daily_walks"
                    }
                },
                "travel": {
                    "button": "Для путешествий",
                    "preview": {
                        "photo": "photo_7",
                        "text": "Для перелётов"
                    },
                    "save": {
                        "usage": "travel"
                    }
                }
            },
            "next_level": 3
        }
    }
}
