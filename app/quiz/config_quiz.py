QUIZ_CONFIG = {

    # =========================
    # Уровень 1 - корень квиза
    # =========================
    "root": {
        1: {
            "photo": "AgACAgIAAxkDAAIxHGlhIkhs6JBDHOwb-AHu0ievep85AAKQC2sbEv8QS5rKL8kjTYlEAQADAgADdwADOAQ",
            "text": (
                "Выберите верное утверждение:\n\n"
                "<blockquote>1. Я в положении. Ищу коляску для новорожденного 🤰</blockquote>\n\n"
                "<blockquote>2. Ищу прогулочную коляску 6+ 👶</blockquote>\n\n"
                "<blockquote>3. Коляска уже есть</blockquote>"
            ),
            "options": {
                "pregnant": {
                    "button": "Я в положении",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIw-mlhHkJ9BbMeFzayJuqoJ_kuuTOZAAJKC2sbEv8QS42H0z1-IipjAQADAgADeAADOAQ",
                        "text": "<blockquote>Коляски для новорожденных детей. Обязательно с люлькой для малыша, а также со сидячим "
                                "блоком и автолюлькой в зависимости от модели и комплектации</blockquote>"
                    },
                    "branch": "pregnant",
                    "save": {"user_type": "group_1"}
                },
                "stroller_6_plus": {
                    "button": "Прогулочная коляска 6+",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxC2lhH445PVA2tPxkwhMO1Se6EbsNAAJiC2sbEv8QS-zOLlSkpksgAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляски для уже подросших детей, способных сидеть. Так называемые "
                                "'прогулочные' коляски более лёгкие и компактные</blockquote>"
                    },
                    "branch": "stroller_6_plus",
                    "save": {"user_type": "group_2"}
                },
                "service_only": {
                    "button": "Коляска уже есть",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxOWlhIlRQWjtMQWFDG_j2m2DgKRqOAAKcC2sbEv8QS1UfoePnMUCvAQADAgADdwADOAQ",
                        "text": "<blockquote>Купить коляску – полдела. Очень важен своевременный уход и знание особых "
                                "нюансов эксплуатации для предотвращения критического износа коляски, а также "
                                "безопасности вашего ребенка\n\n"
                                "❗️Подавляющее большинство поломок не попадает под гарантию производителей и связано "
                                "с незнанием родителей простых, но неочевидных правил использования колясок</blockquote>"
                    },
                    "branch": "service_only",
                    "save": {"user_type": "group_2"}
                },
            },
            "next_level": 2
        }
    },

    # =========================
    # Ветвь "pregnant"
    # =========================
    "pregnant": {
        2: {
            "photo": "AgACAgIAAxkDAAIw_WlhHq-pcY1UuhTjd-so7qsAAcz8VgACUQtrGxL_EEvXYwYoJjNfvgEAAwIAA3kAAzgE",
            "text": "Сфера применения коляски\n\n"
                    "<blockquote>Выберите, для выполнения каких основных задач требуется коляска</blockquote>",
            "options": {
                "daily": {
                    "button": "Для ежедневных прогулок",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIw_mlhHr1CniI5Ab78iqHQ2rRbmPTkAAJSC2sbEv8QSzbFBhmNlWWnAQADAgADeQADOAQ",
                        "text": "<blockquote>Детские коляски для ежедневных прогулок возле дома или в парке</blockquote>"
                    },
                    "save": {"usage": "daily_walks"}
                },
                "autolady": {
                    "button": "Я автоледи",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxIGlhIkmhwlLRl5dvRj8wD_C0ZEKCAAKRC2sbEv8QS5E85t0_MAuRAQADAgADdwADOAQ",
                        "text": "<blockquote>Коляски, которые более компактные, чтобы помещались в багажник автомобиля</blockquote>"
                    },
                    "save": {"usage": "autolady"}
                },
                "travel": {
                    "button": "Для путешествий",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIw_2lhHwM1PihBh5cjowVPdzANcQEJAAJUC2sbEv8QS9m1_R5LMJ5NAQADAgADeQADOAQ",
                        "text": "<blockquote>Как правило, это самые минималистичные и компактные коляски. Некоторые "
                                "модели разрешено проносить в качестве ручной клади на борт самолётов. Такие коляски "
                                "не отличаются высокой проходимостью и предназначены исключительно для ровных "
                                "асфальтированных дорог</blockquote>"
                    },
                    "save": {"usage": "travel"},
                    "finish": True
                },
            },
            "next_level": 3
        },
        3: {
            "photo": "AgACAgIAAxkDAAIvmWlL8xkbwYjDdjiB46Pr6ZzPR3WIAALMEGsb1_tgSsoFcdev5MQdAQADAgADeAADNgQ",
            "text": "Выберите материал коляски",
            "options": {
                "aluminum": {
                    "button": "Алюминий",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIvmmlL8xnBEHDg1biLDPTtKlHrDdlCAALNEGsb1_tgSkirvkvmJOW5AQADAgADeAADNgQ",
                        "text": "Коляска с алюминиевой рамой"
                    },
                    "save": {"frame_material": "aluminum"}
                },
                "steel": {
                    "button": "Сталь",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIvm2lL8xqvOFcn_7scId5LT3hOdo_UAALOEGsb1_tgShr-ys5-yc8iAQADAgADeAADNgQ",
                        "text": "Коляска со стальной рамой"
                    },
                    "save": {"frame_material": "steel"}
                }
            },
            "next_level": None
        }
    },

    # =========================
    # Ветвь "stroller_6_plus" (6+ мес.)
    # =========================
    "stroller_6_plus": {
        2: {
            "photo": "AgACAgIAAxkDAAIvm2lL8xqvOFcn_7scId5LT3hOdo_UAALOEGsb1_tgShr-ys5-yc8iAQADAgADeAADNgQ",
            "text": "Тип прогулочной коляски",
            "options": {
                "compact": {
                    "button": "Компактная",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIvm2lL8xqvOFcn_7scId5LT3hOdo_UAALOEGsb1_tgShr-ys5-yc8iAQADAgADeAADNgQ",
                        "text": "Легкая и удобная для города"
                    },
                    "save": {"stroller_type": "compact"}
                },
                "all_terrain": {
                    "button": "Всё проходимая",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIvm2lL8xqvOFcn_7scId5LT3hOdo_UAALOEGsb1_tgShr-ys5-yc8iAQADAgADeAADNgQ",
                        "text": "Для прогулок по разным покрытиям"
                    },
                    "save": {"stroller_type": "all_terrain"}
                }
            },
            "next_level": 3
        },
        3: {
            "photo": "AgACAgIAAxkDAAIvm2lL8xqvOFcn_7scId5LT3hOdo_UAALOEGsb1_tgShr-ys5-yc8iAQADAgADeAADNgQ",
            "text": "Выберите цвет коляски",
            "options": {
                "red": {
                    "button": "Красная",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIvm2lL8xqvOFcn_7scId5LT3hOdo_UAALOEGsb1_tgShr-ys5-yc8iAQADAgADeAADNgQ",
                        "text": "Красная коляска"
                    },
                    "save": {"color": "red"}
                },
                "blue": {
                    "button": "Синяя",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIvm2lL8xqvOFcn_7scId5LT3hOdo_UAALOEGsb1_tgShr-ys5-yc8iAQADAgADeAADNgQ",
                        "text": "Синяя коляска"
                    },
                    "save": {"color": "blue"}
                }
            },
            "next_level": None
        }
    },

    # =========================
    # Ветвь "service_only" (уже есть коляска)
    # =========================
    "service_only": {
        2: {
            "photo": "AgACAgIAAxkDAAIxGGlhIFRJHrc-Wp_og1wU4y0KryrOAAJ2C2sbEv8QS5o0-r_wkpX_AQADAgADeQADOAQ",
            "text": "Укажите пожалуйста тип вашей коляски\n\n"
                    "<blockquote>В зависимости от типа коляски может отличаться время и частота обслуживания, а "
                    "также некоторые рекомендации по эксплуатации</blockquote>",
            "options": {
                "cleaning": {
                    "button": "Коляска от рождения 0+",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxO2lhIlWf8p-CjgpfYKI6nTY9gi-vAAKdC2sbEv8QS1adHAflDG6xAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляски с люлькой + прогулочный блок и автолюлька (в зависимости от "
                                "комплектации)</blockquote>"
                    },
                    "save": {"service_type": "cleaning"}
                },
                "repair": {
                    "button": "Прогулочная коляска 6+",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxGmlhIFXxO8sdL1t5ysb7M9yRAWULAAJ4C2sbEv8QS0rXGIJ6uqGJAQADAgADeAADOAQ",
                        "text": "<blockquote>Коляска для малышей которые уже умеют сидеть</blockquote>"
                    },
                    "save": {"service_type": "repair"}
                }
            },
            "next_level": None
        }
    }
}

