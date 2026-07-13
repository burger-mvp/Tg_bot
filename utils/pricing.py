"""Расчет цен и сборка неизменяемого текста публикации."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Final


AED_PER_USD: Final = Decimal("3.66")
ENGINE_MARKUP: Final = Decimal("1.10")
BODY_MARKUP: Final = Decimal("1.15")
POST_HEADER: Final = "🇦🇪 🇨🇳 🇷🇺 🇰🇿"
FIXED_FOOTER: Final = """Все запчасти согласовываются с вами в онлайн-режиме, что упрощает процесс. ‼️

Условия доставки:
⚠️ ДВС, КПП и ходовая часть: 2,3$ за кг.
⚠️ Кузовные детали, оптика, машинокомплекты — по запросу.
⚠️ Запчасти для спецтехники Caterpillar, Komatsu, JCB — по запросу.

Для оформления заказа и получения консультации пишите: ✏️
✏️ @Kpp_Motors_Roman
✏️ @zakupUAE
✏️ @Kpp_Motors1
✏️ @Annakppmotors
✏️ @Kpp_Motors
✏️ @IvanSat74

Наш канал на YouTube: https://www.youtube.com/@KppMotors"""


def parse_aed_price(raw_price: str) -> Decimal:
    """Преобразует пользовательскую цену AED в положительное Decimal-значение."""
    normalized = raw_price.strip().replace(" ", "").replace(",", ".")
    try:
        price = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError("Цена не является числом") from error
    if not price.is_finite() or price <= 0:
        raise ValueError("Цена должна быть положительной")
    return price


def convert_aed_to_usd(aed_price: Decimal, markup: Decimal) -> int:
    """Конвертирует AED в USD с заданной наценкой и округлением до целого."""
    return int(((aed_price / AED_PER_USD) * markup).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def serialize_price(aed_price: Decimal, markup: Decimal) -> dict[str, int | str]:
    """Готовит цену для JSONB: исходное AED и рассчитанное целое USD."""
    return {
        "aed": format(aed_price.normalize(), "f"),
        "usd": convert_aed_to_usd(aed_price, markup),
    }


def format_post_text(description: str, post_kind: str, price_data: dict[str, Any]) -> str:
    """Собирает итоговый текст в обязательном порядке: шапка, описание, цены, подвал."""
    if post_kind == "engine_only":
        price_lines = f"Цена ДВС: ${price_data['engine']['usd']} USD"
    elif post_kind == "engine_with_transmission":
        price_lines = (
            f"Цена только ДВС: ${price_data['engine']['usd']} USD\n"
            f"Цена ДВС с АКПП: ${price_data['engine_with_transmission']['usd']} USD"
        )
    elif post_kind == "body":
        price_lines = f"Цена: ${price_data['body']['usd']} USD"
    else:
        raise ValueError(f"Неизвестная категория поста: {post_kind}")

    return f"{POST_HEADER}\n\n{description}\n\n{price_lines}\n\n{FIXED_FOOTER}"
