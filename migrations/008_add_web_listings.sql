-- Объявления сайта, медиафайлы из Bucket и заявки покупателей.

CREATE TABLE IF NOT EXISTS web_listings (
    id UUID PRIMARY KEY,
    post_queue_id UUID UNIQUE REFERENCES post_queue (id) ON DELETE SET NULL,
    author_telegram_id BIGINT REFERENCES users (telegram_id) ON DELETE SET NULL,
    seller_shop_name TEXT NOT NULL DEFAULT '—',
    description TEXT NOT NULL,
    post_kind VARCHAR(32) NOT NULL,
    price_data JSONB NOT NULL CHECK (jsonb_typeof(price_data) = 'object'),
    price_usd INTEGER NOT NULL CHECK (price_usd > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'hidden', 'archived')),
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS web_listing_media (
    id BIGSERIAL PRIMARY KEY,
    listing_id UUID NOT NULL REFERENCES web_listings (id) ON DELETE CASCADE,
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('photo', 'video', 'document')),
    url TEXT NOT NULL,
    object_key TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS web_purchase_requests (
    id BIGSERIAL PRIMARY KEY,
    listing_id UUID NOT NULL REFERENCES web_listings (id) ON DELETE CASCADE,
    phone_number TEXT NOT NULL,
    client_name TEXT,
    notified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS web_listings_active_idx
    ON web_listings (published_at DESC)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS web_listings_expires_at_idx
    ON web_listings (expires_at)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS web_listing_media_listing_idx
    ON web_listing_media (listing_id, sort_order);

CREATE INDEX IF NOT EXISTS web_purchase_requests_listing_idx
    ON web_purchase_requests (listing_id, created_at DESC);
