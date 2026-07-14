"""Расчет цен и сборка неизменяемого текста публикации."""

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Final


AED_PER_USD: Final = Decimal("3.66")
ENGINE_MARKUP: Final = Decimal("1.10")
BODY_MARKUP: Final = Decimal("1.15")
POST_HEADER: Final = "🇦🇪 🇨🇳 🇷🇺 🇰🇿"
TELEGRAM_CAPTION_LIMIT: Final = 1_024
_TRUNCATION_SUFFIX: Final = "..."
RU_FIXED_FOOTER: Final = """Все запчасти согласовываются с вами в онлайн-режиме, что упрощает процесс. ‼️

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

Наш канал на YouTube: https://www.youtube.com/@KppMotors

Продавец: {seller_name}"""
EN_FIXED_FOOTER: Final = """All parts are agreed with you online, which makes the process easier. ‼️

Delivery terms:
⚠️ Engine, gearbox and suspension parts: $2.3 per kg.
⚠️ Body parts, optics, vehicle kits — on request.
⚠️ Parts for Caterpillar, Komatsu, JCB special equipment — on request.

To place an order or get advice, contact: ✏️
✏️ @Kpp_Motors_Roman
✏️ @zakupUAE
✏️ @Kpp_Motors1
✏️ @Annakppmotors
✏️ @Kpp_Motors
✏️ @IvanSat74

Our YouTube channel: https://www.youtube.com/@KppMotors

Seller: {seller_name}"""


def round_price_up_to_tens(price: Decimal) -> Decimal:
    """Округляет цену вверх до ближайшего десятка для красивого отображения."""
    return Decimal(math.ceil(float(price) / 10) * 10)


def parse_aed_price(raw_price: str) -> Decimal:
    """Принимает только целую положительную AED-цену без пробелов и символов."""
    if not raw_price.isascii() or not raw_price.isdecimal():
        raise ValueError("Цена должна состоять только из цифр")
    try:
        price = Decimal(raw_price)
    except InvalidOperation as error:
        raise ValueError("Цена не является числом") from error
    if not price.is_finite() or price <= 0:
        raise ValueError("Цена должна быть положительной")
    # Округляем цену вверх до десятков
    return round_price_up_to_tens(price)


def _telegram_length(text: str) -> int:
    """Считает длину так же, как ограничения Telegram: в UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def _truncate_for_telegram(text: str, max_length: int) -> str:
    """Обрезает строку по лимиту Telegram, не разрывая Unicode-символы."""
    result: list[str] = []
    current_length = 0
    for character in text:
        character_length = _telegram_length(character)
        if current_length + character_length > max_length:
            break
        result.append(character)
        current_length += character_length
    return "".join(result)


def convert_aed_to_usd(aed_price: Decimal, markup: Decimal) -> int:
    """Конвертирует AED в USD с заданной наценкой и округлением до целого."""
    return int(((aed_price / AED_PER_USD) * markup).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def serialize_price(aed_price: Decimal, markup: Decimal) -> dict[str, int | str]:
    """Готовит цену для JSONB: исходное AED и рассчитанное целое USD."""
    return {
        "aed": format(aed_price.normalize(), "f"),
        "usd": convert_aed_to_usd(aed_price, markup),
    }


def format_post_text(
    description: str,
    post_kind: str,
    price_data: dict[str, Any],
    seller_name: str = "",
    language_code: str = "ru",
) -> str:
    """Собирает итоговый текст в обязательном порядке: шапка, описание, цены, подвал с подписью продавца."""
    is_russian = language_code == "ru"
    if post_kind == "engine_only":
        label = "Цена ДВС" if is_russian else "Engine price"
        price_lines = f"{label}: ${price_data['engine']['usd']} USD"
    elif post_kind == "engine_with_transmission":
        engine_label = "Цена только ДВС" if is_russian else "Engine only price"
        set_label = "Цена ДВС с АКПП" if is_russian else "Engine with Gearbox price"
        price_lines = (
            f"{engine_label}: ${price_data['engine']['usd']} USD\n"
            f"{set_label}: ${price_data['engine_with_transmission']['usd']} USD"
        )
    elif post_kind == "body":
        label = "Цена" if is_russian else "Price"
        price_lines = f"{label}: ${price_data['body']['usd']} USD"
    else:
        raise ValueError(f"Неизвестная категория поста: {post_kind}")

    footer_template = RU_FIXED_FOOTER if is_russian else EN_FIXED_FOOTER
    footer = footer_template.format(seller_name=seller_name or "—")
    return f"{POST_HEADER}\n\n{description}\n\n{price_lines}\n\n{footer}"


def format_post_caption(
    description: str,
    post_kind: str,
    price_data: dict[str, Any],
    seller_name: str = "",
    language_code: str = "ru",
) -> str:
    """Формирует подпись до 1024 символов, сокращая только пользовательское описание."""
    post_text = format_post_text(description, post_kind, price_data, seller_name, language_code)
    if _telegram_length(post_text) <= TELEGRAM_CAPTION_LIMIT:
        return post_text

    fixed_text_length = _telegram_length(format_post_text("", post_kind, price_data, seller_name, language_code))
    description_limit = TELEGRAM_CAPTION_LIMIT - fixed_text_length - _telegram_length(_TRUNCATION_SUFFIX)
    if description_limit < 1:
        raise ValueError("Обязательная часть поста превышает лимит подписи Telegram")
    shortened_description = f"{_truncate_for_telegram(description, description_limit).rstrip()}{_TRUNCATION_SUFFIX}"
    return format_post_text(shortened_description, post_kind, price_data, seller_name, language_code)
