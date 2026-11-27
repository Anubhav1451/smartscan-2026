# SmartScan 2026 - Schema SQL

Run this ONCE in the existing Supabase project: **SQL Editor → New query → paste → Run.**
It creates a fresh schema `app2026` for the new build. The old app's data (public schema) is **not touched**.

After running it, also do this one setting: **Dashboard → Settings → API → Exposed schemas → add `app2026`** (next to `public`). Without this the API cannot see the new schema.

```sql
create schema if not exists app2026;

create table app2026.retailers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table app2026.stores (
  id uuid primary key default gen_random_uuid(),
  retailer_id uuid references app2026.retailers(id),
  name text not null,
  code text not null unique,
  area text,
  address text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table app2026.products (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references app2026.stores(id) on delete cascade,
  barcode text not null,
  name text not null,
  brand text,
  category text,
  price integer not null check (price >= 0),
  mrp integer,
  stock integer not null default 0 check (stock >= 0),
  unit text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (store_id, barcode)
);

create table app2026.profiles (
  id uuid primary key,
  email text,
  role text not null default 'customer' check (role in ('customer', 'manager', 'exit_staff')),
  store_id uuid references app2026.stores(id),
  created_at timestamptz not null default now()
);

create table app2026.orders (
  id uuid primary key default gen_random_uuid(),
  bill_no text unique,
  store_id uuid not null references app2026.stores(id),
  customer_id uuid,
  total integer not null default 0,
  payment_method text check (payment_method in ('mock_upi', 'card', 'cash')),
  payment_status text not null default 'PENDING' check (payment_status in ('PENDING', 'PAID', 'CASH_PENDING')),
  status text not null default 'PENDING',
  created_at timestamptz not null default now(),
  paid_at timestamptz
);

create table app2026.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references app2026.orders(id) on delete cascade,
  product_id uuid references app2026.products(id),
  barcode text,
  name text,
  price integer not null,
  qty integer not null check (qty > 0)
);

create table app2026.exit_verifications (
  id uuid primary key default gen_random_uuid(),
  order_id uuid references app2026.orders(id),
  bill_no text,
  result text not null,
  verified_by uuid,
  created_at timestamptz not null default now()
);

create table app2026.unknown_scans (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references app2026.stores(id) on delete cascade,
  barcode text not null,
  count integer not null default 1 check (count > 0),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  unique (store_id, barcode)
);

create index idx_products_store on app2026.products (store_id);
create index idx_orders_store on app2026.orders (store_id);
create index idx_order_items_order on app2026.order_items (order_id);
create index idx_unknown_store on app2026.unknown_scans (store_id);

alter table app2026.retailers enable row level security;
alter table app2026.stores enable row level security;
alter table app2026.products enable row level security;
alter table app2026.profiles enable row level security;
alter table app2026.orders enable row level security;
alter table app2026.order_items enable row level security;
alter table app2026.exit_verifications enable row level security;
alter table app2026.unknown_scans enable row level security;

grant usage on schema app2026 to service_role, authenticated, anon;
grant all on all tables in schema app2026 to service_role;
grant select, insert, update, delete on all tables in schema app2026 to authenticated;
```

Backend note: create the Supabase client with the schema set - Python: `create_client(url, key, options=ClientOptions(schema="app2026"))`. The backend uses the service-role key, which bypasses RLS; all data access goes through the backend only.
