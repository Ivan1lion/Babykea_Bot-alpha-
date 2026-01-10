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
            "photo": "AgACAgIAAxkDAAIxImlhIkrQvb4IbZpimQ-2Pe4-KKjmAAKSC2sbEv8QSwntknxqUya9AQADAgADeQADOAQ",
            "text": "Коляска для зимы или для лета?\n\n"
                    "<blockquote>При выборе коляски нужно учитывать, на какое время года выпадают первые 6 месяцев "
                    "жизни ребёнка. От этого зависит тип и размер люльки, а также проходимость шасси</blockquote>",
            "options": {
                "leto": {
                    "button": "Тёплое время года",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxdWliU-Bv0VkENR8e24a7ElnibL8vAAIaEGsbOZkQS2Zoa89NJLTcAQADAgADeQADOAQ",
                        "text": "<blockquote>Для тёплого периода отлично подходят тканевые люльки (складные на распорках). Такие "
                                "люльки мало весят, компактно складываются и хорошо дышат за счёт дополнительных "
                                "секций для проветривания</blockquote>"
                    },
                    "save": {"vremya_goda": "leto"}
                },
                "zima": {
                    "button": "Холодное время года",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxdmliU_Ig2e7_a1dkdwZQsCKLbverAAIeEGsbOZkQS1mqqnoV_se2AQADAgADeQADOAQ",
                        "text": "<blockquote>На холодный период рекомендуются люльки из пластика и термолюльки. Они отличаются "
                                "большим размером и глубиной, чтобы подросшему крохе в тёплом конверте "
                                "(зимней одежде) не было тесно</blockquote>"
                    },
                    "save": {"vremya_goda": "zima"}
                }
            },
            "next_level": 4
        },
        4: {
            "photo": "AgACAgIAAxkDAAIxAAFpYR9FeZiN3xBqV8zu4GQGeyVyNAACVQtrGxL_EEsHwk3bWiUdBAEAAwIAA3kAAzgE",
            "text": "Желаемый функционал\n\n"
                    "<blockquote>Выберете предпочтительный для вас фукционал коляски</blockquote>",
            "options": {
                "2in1": {
                    "button": "2 в 1",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxA2lhH2vJ6Bt48gxuveynfK49bJExAAJYC2sbEv8QS-890ddSdERpAQADAgADdwADOAQ",
                        "text": "<blockquote>Модульная коляска с двумя сменными блоками. Люлька и сидячий блок</blockquote>"
                    },
                    "save": {"funkcional": "2in1"}
                },
                "3in1": {
                    "button": "3 в 1",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxJWlhIksVxtKNBa1BENCyz68PDOrXAAKTC2sbEv8QSy4VrYTg9ufeAQADAgADdwADOAQ",
                        "text": "<blockquote>Люлька, сидячий блок + автолюлька для перевозки новорожденного (до 3х "
                                "месяцев) в автомобиле</blockquote>"
                    },
                    "save": {"funkcional": "3in1"}
                },
                "transformer": {
                    "button": "Трансформер",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxJmlhIkvPndJ0-0GTmuuyCTSj_efTAAKUC2sbEv8QS0cWwgcRVVKOAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляска у которой люлька по средствам регуляции тросиков или "
                                "строп трансформируется в сидячий блок. Практичные, но менее комфортные "
                                "коляски</blockquote>"
                    },
                    "save": {"funkcional": "transformer"}
                }
            },
            "next_level": 5
        },
        5: {
            "photo": "AgACAgIAAxkDAAIxBmlhH3Z9Dn3FgqklPnajz_ZQwN3wAAJcC2sbEv8QS84pEuGqzo7tAQADAgADeQADOAQ",
            "text": "Тип дороги преимущественно по которому будете ездить\n\n"
                    "<blockquote>Очень важно определить тип дорог вашей местности. От этого зависит на сколько "
                    "удобным будет управление коляской и комфорт малыша</blockquote>",
            "options": {
                "grynt": {
                    "button": "Грунт",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxB2lhH3oqjnS8aCU2unE1ryLbcdeWAAJdC2sbEv8QS-ngqRnZB1ihAQADAgADeQADOAQ",
                        "text": "<blockquote>Детская коляска подходящая для передвижения по грунту. Большие колёса, "
                                "крепкая рама - если живёте за городом</blockquote>"
                    },
                    "save": {"tip_dorogi": "grynt"}
                },
                "asfalt": {
                    "button": "Алфальт",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxCGlhH32H2Mhd3sbANA-bCT6h6EbxAAJeC2sbEv8QSxA_DXnKTulGAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляска может иметь маленькие колеса и минимальный размер (массу) "
                                "шасси</blockquote>"
                    },
                    "save": {"tip_dorogi": "asfalt"}
                },
                "combo": {
                    "button": "Комбинированный",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxCWlhH3_d0nBQH6ZQoZ7qHexOdwHrAAJfC2sbEv8QSzH_B-ea_v4LAQADAgADeAADOAQ",
                        "text": "<blockquote>Детская коляска подходящая для передвижения по грунту, асфальту "
                                "или плитке. Обладает средним размером колёс и неплохой системой амортизации</blockquote>"
                    },
                    "save": {"tip_dorogi": "combo"}
                },
                "off_road": {
                    "button": "Off-road",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxCmlhH4naMSKH52Py0ikdakBza8ftAAJhC2sbEv8QS6G-L6GqRQNEAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляски-вездеходы способны преодолевать бездорожье. Для таких колясок "
                                "характерны четыре одинаковых больших колеса и массивная рама. Они менее поворотливы "
                                "и тяжелы. Но если нужно уходить от погони по снегу – это идеальный вариант. Выбор "
                                "родителей из северных регионов</blockquote>"
                    },
                    "save": {"tip_dorogi": "off_road"}
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

