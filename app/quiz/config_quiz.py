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
                    "save": {"stroller_type": "from_birth"}
                },
                "stroller_6_plus": {
                    "button": "Прогулочная коляска 6+",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxC2lhH445PVA2tPxkwhMO1Se6EbsNAAJiC2sbEv8QS-zOLlSkpksgAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляски для уже подросших детей, способных сидеть. Так называемые "
                                "'прогулочные' коляски более лёгкие и компактные</blockquote>"
                    },
                    "branch": "stroller_6_plus",
                    "save": {"stroller_type": "stroller"}
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
                    "save": {"user_type": "service_only"}
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
                "daily_walks": {
                    "button": "Для ежедневных прогулок",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIw_mlhHr1CniI5Ab78iqHQ2rRbmPTkAAJSC2sbEv8QSzbFBhmNlWWnAQADAgADeQADOAQ",
                        "text": "<blockquote>Детские коляски для ежедневных прогулок возле дома или в парке</blockquote>"
                    },
                    "save": {"usage_format": "daily_walks"}
                },
                "autolady": {
                    "button": "Я автоледи",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxIGlhIkmhwlLRl5dvRj8wD_C0ZEKCAAKRC2sbEv8QS5E85t0_MAuRAQADAgADdwADOAQ",
                        "text": "<blockquote>Коляски, которые более компактные, чтобы помещались в багажник автомобиля</blockquote>"
                    },
                    "save": {"usage_format": "car_trips"}
                },
                "air_travel": {
                    "button": "Для путешествий",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIw_2lhHwM1PihBh5cjowVPdzANcQEJAAJUC2sbEv8QS9m1_R5LMJ5NAQADAgADeQADOAQ",
                        "text": "<blockquote>Как правило, это самые минималистичные и компактные коляски. Некоторые "
                                "модели разрешено проносить в качестве ручной клади на борт самолётов. Такие коляски "
                                "не отличаются высокой проходимостью и предназначены исключительно для ровных "
                                "асфальтированных дорог</blockquote>"
                    },
                    "save": {"usage_format": "air_travel"},
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
                "summer": {
                    "button": "Тёплое время года",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxdWliU-Bv0VkENR8e24a7ElnibL8vAAIaEGsbOZkQS2Zoa89NJLTcAQADAgADeQADOAQ",
                        "text": "<blockquote>Для тёплого периода отлично подходят тканевые люльки (складные на распорках). Такие "
                                "люльки мало весят, компактно складываются и хорошо дышат за счёт дополнительных "
                                "секций для проветривания</blockquote>"
                    },
                    "save": {"season_start": "summer"}
                },
                "winter": {
                    "button": "Холодное время года",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxdmliU_Ig2e7_a1dkdwZQsCKLbverAAIeEGsbOZkQS1mqqnoV_se2AQADAgADeQADOAQ",
                        "text": "<blockquote>На холодный период рекомендуются люльки из пластика и термолюльки. Они отличаются "
                                "большим размером и глубиной, чтобы подросшему крохе в тёплом конверте "
                                "(зимней одежде) не было тесно</blockquote>"
                    },
                    "save": {"season_start": "winter"}
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
                    "save": {"from_birth_subtype": "2in1"}
                },
                "3in1": {
                    "button": "3 в 1",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxJWlhIksVxtKNBa1BENCyz68PDOrXAAKTC2sbEv8QSy4VrYTg9ufeAQADAgADdwADOAQ",
                        "text": "<blockquote>Люлька, сидячий блок + автолюлька для перевозки новорожденного (до 3х "
                                "месяцев) в автомобиле</blockquote>"
                    },
                    "save": {"from_birth_subtype": "3in1"}
                },
                "transformer": {
                    "button": "Трансформер",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxJmlhIkvPndJ0-0GTmuuyCTSj_efTAAKUC2sbEv8QS0cWwgcRVVKOAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляска у которой люлька по средствам регуляции тросиков или "
                                "строп трансформируется в сидячий блок. Практичные, но менее комфортные "
                                "коляски</blockquote>"
                    },
                    "save": {"from_birth_subtype": "transformer"}
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
                "ground": {
                    "button": "Грунт",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxB2lhH3oqjnS8aCU2unE1ryLbcdeWAAJdC2sbEv8QS-ngqRnZB1ihAQADAgADeQADOAQ",
                        "text": "<blockquote>Детская коляска подходящая для передвижения по грунту. Большие колёса, "
                                "крепкая рама - если живёте за городом</blockquote>"
                    },
                    "save": {"road_conditions": "ground"}
                },
                "asphalt": {
                    "button": "Аcфальт",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxCGlhH32H2Mhd3sbANA-bCT6h6EbxAAJeC2sbEv8QSxA_DXnKTulGAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляска может иметь маленькие колеса и минимальный размер (массу) "
                                "шасси</blockquote>"
                    },
                    "save": {"road_conditions": "asphalt"}
                },
                "combination": {
                    "button": "Комбинированный",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxCWlhH3_d0nBQH6ZQoZ7qHexOdwHrAAJfC2sbEv8QSzH_B-ea_v4LAQADAgADeAADOAQ",
                        "text": "<blockquote>Детская коляска подходящая для передвижения по грунту, асфальту "
                                "или плитке. Обладает средним размером колёс и неплохой системой амортизации</blockquote>"
                    },
                    "save": {"road_conditions": ["ground and asphalt"]}
                },
                "offroad": {
                    "button": "Off-road",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxCmlhH4naMSKH52Py0ikdakBza8ftAAJhC2sbEv8QS6G-L6GqRQNEAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляски-вездеходы способны преодолевать бездорожье. Для таких колясок "
                                "характерны четыре одинаковых больших колеса и массивная рама. Они менее поворотливы "
                                "и тяжелы. Но если нужно уходить от погони по снегу – это идеальный вариант. Выбор "
                                "родителей из северных регионов</blockquote>"
                    },
                    "save": {"road_conditions": "offroad and snow"}
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
            "photo": "AgACAgIAAxkDAAIxLWlhIk7G50gOv8PZBfd6LvA_RGL3AAKVC2sbEv8QSyWutC5mNf-vAQADAgADdwADOAQ",
            "text": "Сфера применения коляски\n\n"
                    "<blockquote>Выберите, для выполнения каких основных задач требуется коляска</blockquote>",
            "options": {
                "daily_walks": {
                    "button": "Для ежедневных прогулок",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxDWlhH5pVOCaa31wNhQAB_zvSu-cbsgACZAtrGxL_EEuncPZuBmzt4AEAAwIAA3kAAzgE",
                        "text": "<blockquote>Детские коляски для ежедневных прогулок возле дома или в парке</blockquote>"
                    },
                    "save": {"usage_format": "daily_walks"}
                },
                "autolady": {
                    "button": "Я автоледи",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxL2lhIk-jy2KFsRB4bMsTh9CGvlhvAAKWC2sbEv8QSyyhM67R2cs4AQADAgADeQADOAQ",
                        "text": "<blockquote>Коляски, которые более компактные, чтобы помещались в багажник автомобиля</blockquote>"
                    },
                    "save": {"usage_format": "car_trips"}
                },
                "air_travel": {
                    "button": "Для путешествий",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxMGlhIlBBAyWdCUIFg2Db--PLsP8DAAKXC2sbEv8QS0slgEGbq_10AQADAgADdwADOAQ",
                        "text": "<blockquote>Как правило, это самые минималистичные и компактные коляски. Некоторые "
                                "модели разрешено проносить в качестве ручной клади на борт самолётов. Такие коляски "
                                "не отличаются высокой проходимостью и предназначены исключительно для ровных "
                                "асфальтированных дорог</blockquote>"
                    },
                    "save": {"usage_format": "air_travel"},
                    "finish": True
                },
            },
            "next_level": 3
        },
        3: {
            "photo": "AgACAgIAAxkDAAIxEGlhH9V1TIhe3iLApYnqx5sOMEylAAJqC2sbEv8QSz3xBUJWCS8CAQADAgADeAADOAQ",
            "text": "Тип ручки коляски\n\n"
                    "<blockquote>От типа ручки зависит тип складывания коляски и её функциональность</blockquote>",
            "options": {
                "koljaska-trost": {
                    "button": "Раздельная",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxMmlhIlGGCXSIgYzv_KTHMlfccY6dAAKZC2sbEv8QS2wHadb8hek7AQADAgADdwADOAQ",
                        "text": "<blockquote>Коляски с таким типом ручек называются «коляски-трости». Зачастую имеют очень "
                                "слабую проходимость и ограниченную функциональность. Тяжело вести коляску "
                                "одной рукой</blockquote>"
                    },
                    "save": {"subtype": "stroller_folds_like_a_cane"}
                },
                "progylka": {
                    "button": "Цельная",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxM2lhIlIJXyZ3LiDO5WslMxFBuEsTAAKaC2sbEv8QS7Qx1qthkXKeAQADAgADdwADOAQ",
                        "text": "<blockquote>Самый распространённый вид прогулочных колясок. Идеально подходит для ежедневного "
                                "использования</blockquote>"
                    },
                    "save": {"subtype": "The_child's_age_is_from_6_months"}
                }
            },
            "next_level": 4
        },
        4: {
            "photo": "AgACAgIAAxkDAAIxE2lhIBOwy3kU5LAiqECkab_Lzby8AAJwC2sbEv8QSyiNAiAqIovPAQADAgADeAADOAQ",
            "text": "Тип дороги преимущественно по которому будете ездить\n\n"
                    "<blockquote>Очень важно определить тип дорог вашей местности. От этого зависит на сколько "
                    "удобным будет управление коляской и комфорт малыша</blockquote>",
            "options": {
                "ground": {
                    "button": "Грунт",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxFGlhIBiJUKFOzyP91iyKC58fWtslAAJxC2sbEv8QSz43VSQc2YAGAQADAgADeAADOAQ",
                        "text": "<blockquote>Детская коляска подходящая для передвижения по грунту. Большие колёса, "
                                "крепкая рама - если живёте за городом</blockquote>"
                    },
                    "save": {"road_conditions": ["ground", "soil"]}
                },
                "asphalt": {
                    "button": "Аcфальт",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxFWlhIBwfX8zMUtV2dW9i13aigeSvAAJyC2sbEv8QS13_ZRHMeE5VAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляска может иметь маленькие колеса и минимальный размер (массу) "
                                "шасси</blockquote>"
                    },
                    "save": {"road_conditions": "asphalt"}
                },
                "combination": {
                    "button": "Комбинированный",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxN2lhIlO30NiQrp4qLnfAsCB_wE6UAAKbC2sbEv8QS9oRKJbuslSwAQADAgADdwADOAQ",
                        "text": "<blockquote>Детская коляска подходящая для передвижения по грунту, асфальту "
                                "или плитке. Обладает средним размером колёс и неплохой системой амортизации</blockquote>"
                    },
                    "save": {"road_conditions": ["soil", "asphalt"]}
                },
                "offroad": {
                    "button": "Off-road",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxF2lhIFM3OMOTFjyGEaRjROXQ2zrWAAJ1C2sbEv8QS-6J447-FN8hAQADAgADdwADOAQ",
                        "text": "<blockquote>Коляски-вездеходы способны преодолевать бездорожье. Для таких колясок "
                                "характерны большие колеса и массивная рама. Они менее компактны в сложенном состоянии "
                                "и достаточно тяжелы. Но если нужно уходить от погони по снегу – это идеальный вариант. "
                                "Выбор родителей из северных регионов</blockquote>"
                    },
                    "save": {"road_conditions": ["offroad", "snow"]}
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
                "pregnant": {
                    "button": "Коляска от рождения 0+",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxO2lhIlWf8p-CjgpfYKI6nTY9gi-vAAKdC2sbEv8QS1adHAflDG6xAQADAgADeQADOAQ",
                        "text": "<blockquote>Коляски с люлькой + прогулочный блок и автолюлька (в зависимости от "
                                "комплектации)</blockquote>"
                    },
                    "save": {"stroller_type": "from_birth"}
                },
                "stroller_6_plus": {
                    "button": "Прогулочная коляска 6+",
                    "preview": {
                        "photo": "AgACAgIAAxkDAAIxGmlhIFXxO8sdL1t5ysb7M9yRAWULAAJ4C2sbEv8QS0rXGIJ6uqGJAQADAgADeAADOAQ",
                        "text": "<blockquote>Коляска для малышей которые уже умеют сидеть</blockquote>"
                    },
                    "save": {"stroller_type": "stroller"}
                }
            },
            "next_level": None
        }
    }
}

