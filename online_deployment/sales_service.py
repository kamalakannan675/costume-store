"""
COSTUME STORE — Advanced Sales Analytics, Reporting & Export Service
Engineered for local-first Flask e-commerce platform.
Calculates accurate sales metrics, KPI statistics, product performance,
payment distributions, and renders PDF, Excel (.xlsx), and CSV exports.
"""

from datetime import datetime, date, timedelta
import io
import csv
from sqlalchemy import func, or_, desc

from models import db, Order, OrderItem, Product, ProductVariant, Category, User, PaymentTransaction


SUPPORTED_ORDER_STATUSES = [
    'Pending',
    'Confirmed',
    'Processing',
    'Shipped',
    'Out for Delivery',
    'Delivered',
    'Cancelled',
    'Returned'
]


# ==============================================================================
# 1. DATE RANGE PARSER & HELPERS
# ==============================================================================

def resolve_date_range(period='this_month', start_date_str=None, end_date_str=None):
    """
    Resolves standard or custom date range into naive UTC datetime boundaries (start_dt, end_dt).
    Guarantees start_dt <= end_dt.
    Supported periods: 'today', 'yesterday', 'this_week', 'this_month', 'this_year', 'custom'.
    """
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59, 999999)

    period = (period or 'this_month').lower().strip()

    if period == 'today':
        return today_start, today_end, "Today"

    elif period == 'yesterday':
        y_start = today_start - timedelta(days=1)
        y_end = datetime(y_start.year, y_start.month, y_start.day, 23, 59, 59, 999999)
        return y_start, y_end, "Yesterday"

    elif period == 'this_week':
        # Start from Monday of the current week
        week_start = today_start - timedelta(days=now.weekday())
        return week_start, today_end, "This Week"

    elif period == 'this_month':
        month_start = datetime(now.year, now.month, 1, 0, 0, 0)
        return month_start, today_end, "This Month"

    elif period == 'this_year':
        year_start = datetime(now.year, 1, 1, 0, 0, 0)
        return year_start, today_end, "This Year"

    elif period == 'custom':
        s_dt = None
        e_dt = None
        if start_date_str:
            try:
                d = datetime.strptime(start_date_str.strip(), '%Y-%m-%d')
                s_dt = datetime(d.year, d.month, d.day, 0, 0, 0)
            except ValueError:
                pass
        if end_date_str:
            try:
                d = datetime.strptime(end_date_str.strip(), '%Y-%m-%d')
                e_dt = datetime(d.year, d.month, d.day, 23, 59, 59, 999999)
            except ValueError:
                pass

        if not s_dt:
            s_dt = today_start - timedelta(days=30)
        if not e_dt:
            e_dt = today_end

        if s_dt > e_dt:
            s_dt, e_dt = e_dt, s_dt  # Swap to enforce s_dt <= e_dt safely

        label = f"{s_dt.strftime('%d %b %Y')} to {e_dt.strftime('%d %b %Y')}"
        return s_dt, e_dt, label

    # Default fallback to this month
    month_start = datetime(now.year, now.month, 1, 0, 0, 0)
    return month_start, today_end, "This Month"


# ==============================================================================
# FINANCIAL ACCOUNTING & REVENUE RECOGNITION HELPERS
# ==============================================================================

def get_order_refund_amount(order):
    """
    Computes total refund amount for an order.
    1. If order_status == 'Returned' or payment_status == 'refunded', returns order.total_amount.
    2. If payment_status == 'partially_refunded', inspects PaymentTransaction records with status == 'refunded'
       for this order. If present, returns sum of amount_paise / 100.0.
       If none present in PaymentTransaction, checks order.notes for logged refund amount.
    3. Returns 0.0 otherwise.
    """
    if not order:
        return 0.0
    pay_status = (order.payment_status or '').lower().strip()
    ord_status = (order.order_status or '').strip()

    # Full refund / full return
    if ord_status == 'Returned' or pay_status == 'refunded':
        return float(order.total_amount or 0.0)

    # Partial refund
    if pay_status == 'partially_refunded':
        refund_txns = PaymentTransaction.query.filter_by(order_id=order.id, status='refunded').all()
        if refund_txns:
            return round(sum((t.amount_paise or 0) / 100.0 for t in refund_txns), 2)
        if order.notes:
            m = re.search(r"refund(?:ed)?\s*[:=-]?\s*(?:₹|inr|rs\.?)?\s*([\d,]+(?:\.\d{1,2})?)", order.notes, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1).replace(',', ''))
                except ValueError:
                    pass
    return 0.0


def is_order_recognized_sale(order):
    """
    Determines if an order qualifies as a recognized financial sale.
    Strictly excludes:
    - Cancelled orders (order_status == 'Cancelled')
    - Returned orders (order_status == 'Returned')
    - Fully refunded orders (payment_status == 'refunded')
    - Failed payments (payment_status == 'failed')
    - Pending / unpaid orders (payment_status in ('pending', 'unpaid'))
    Includes:
    - Successfully paid/collected orders (payment_status in ('paid', 'collected', 'partially_refunded'))
      where order_status not in ('Cancelled', 'Returned')
    """
    if not order:
        return False
    if order.order_status in ('Cancelled', 'Returned'):
        return False
    pay_status = (order.payment_status or '').lower().strip()
    if pay_status in ('failed', 'pending', 'unpaid', 'refunded'):
        return False
    return pay_status in ('paid', 'collected', 'partially_refunded')


def get_order_recognized_revenue(order):
    """
    Returns net recognized revenue for an order after deducting refunds.
    Returns 0.0 if the order is not an eligible recognized sale.
    """
    if not is_order_recognized_sale(order):
        return 0.0
    refund = get_order_refund_amount(order)
    net_rev = (order.total_amount or 0.0) - refund
    return max(0.0, round(net_rev, 2))


# ==============================================================================
# 2. ADVANCED ADMIN DASHBOARD ANALYTICS
# ==============================================================================

def get_dashboard_analytics():
    """
    Computes real-time sales KPIs, inventory levels, top-selling costumes,
    recent order stream, and order status distribution for the main admin dashboard.
    Strictly enforces revenue recognition: excludes cancelled, returned, refunded,
    failed, and pending orders. Correctly handles partial refunds.
    """
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    yesterday_start = today_start - timedelta(days=1)

    # 1. Fetch candidate orders for recognized sales
    candidate_orders = Order.query.filter(
        Order.payment_status.in_(['paid', 'collected', 'partially_refunded']),
        ~Order.order_status.in_(['Cancelled', 'Returned']),
        Order.payment_status != 'refunded'
    ).all()

    recognized_orders = [o for o in candidate_orders if is_order_recognized_sale(o)]
    recognized_order_ids = [o.id for o in recognized_orders]

    # Total recognized revenue
    total_revenue = round(sum(get_order_recognized_revenue(o) for o in recognized_orders), 2)

    # Previous 30 days comparison for revenue
    p30_start = today_start - timedelta(days=30)
    p60_start = today_start - timedelta(days=60)
    rev_last_30 = round(sum(
        get_order_recognized_revenue(o) for o in recognized_orders
        if o.created_at and o.created_at >= p30_start
    ), 2)
    rev_prev_30 = round(sum(
        get_order_recognized_revenue(o) for o in recognized_orders
        if o.created_at and p60_start <= o.created_at < p30_start
    ), 2)

    rev_diff = round(rev_last_30 - rev_prev_30, 2)
    rev_change_pct = None
    if rev_prev_30 > 0:
        rev_change_pct = round(((rev_last_30 - rev_prev_30) / rev_prev_30) * 100.0, 1)

    # 2. KPI: Orders Today & Orders Yesterday (Recognized Orders)
    orders_today = sum(1 for o in recognized_orders if o.created_at and o.created_at >= today_start)
    orders_yesterday = sum(1 for o in recognized_orders if o.created_at and yesterday_start <= o.created_at < today_start)

    # 3. KPI: Total Orders & Customers
    total_orders = Order.query.count()
    total_customers = User.query.filter_by(is_admin=False).count()

    # 4. Inventory Status (In-stock, Low-stock <= 5, Out-of-stock == 0)
    total_variants = ProductVariant.query.filter_by(is_active=True).count()
    in_stock_variants = ProductVariant.query.filter(
        ProductVariant.is_active == True,
        ProductVariant.stock_quantity > 5
    ).count()
    low_stock_variants = ProductVariant.query.filter(
        ProductVariant.is_active == True,
        ProductVariant.stock_quantity > 0,
        ProductVariant.stock_quantity <= 5
    ).count()
    out_of_stock_variants = ProductVariant.query.filter(
        ProductVariant.is_active == True,
        ProductVariant.stock_quantity == 0
    ).count()

    low_stock_items = ProductVariant.query.filter(
        ProductVariant.is_active == True,
        ProductVariant.stock_quantity <= 5
    ).order_by(ProductVariant.stock_quantity.asc()).limit(8).all()

    # 5. Top-Selling Products (Exclusively from recognized completed sales)
    top_selling_products = []
    if recognized_order_ids:
        top_selling_rows = db.session.query(
            OrderItem.product_id,
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label('units_sold'),
            func.sum(OrderItem.total_price).label('revenue')
        ).filter(OrderItem.order_id.in_(recognized_order_ids))\
         .group_by(OrderItem.product_id, OrderItem.product_name)\
         .order_by(desc('units_sold'))\
         .limit(5)\
         .all()

        for row in top_selling_rows:
            prod = db.session.get(Product, row.product_id) if row.product_id else None
            image_url = prod.primary_image if prod else '/static/images/placeholder-costume.jpg'
            rev_val = round(float(row.revenue or 0.0), 2)
            top_selling_products.append({
                'product_id': row.product_id,
                'name': row.product_name,
                'sku': prod.sku if prod else 'N/A',
                'units_sold': int(row.units_sold or 0),
                'revenue': rev_val,
                'gross_revenue': rev_val,
                'net_revenue': rev_val,
                'image_url': image_url
            })

    # 6. Recent Orders
    recent_orders = Order.query.order_by(desc(Order.created_at)).limit(8).all()

    # 7. Order Status Statistics
    status_counts = {}
    for st in SUPPORTED_ORDER_STATUSES:
        status_counts[st] = 0

    order_status_query = db.session.query(
        Order.order_status,
        func.count(Order.id)
    ).group_by(Order.order_status).all()

    for st_name, cnt in order_status_query:
        status_counts[st_name] = cnt

    return {
        'kpis': {
            'total_revenue': round(float(total_revenue), 2),
            'orders_today': orders_today,
            'orders_yesterday': orders_yesterday,
            'total_orders': total_orders,
            'total_customers': total_customers,
            'rev_last_30': round(float(rev_last_30), 2),
            'rev_prev_30': round(float(rev_prev_30), 2),
            'prev_revenue_30d': round(float(rev_prev_30), 2),
            'revenue_30d': round(float(rev_last_30), 2),
            'rev_diff': round(float(rev_diff), 2),
            'rev_change_pct': rev_change_pct,
            'rev_growth_pct': rev_change_pct
        },
        'inventory': {
            'total_variants': total_variants,
            'in_stock': in_stock_variants,
            'low_stock': low_stock_variants,
            'out_of_stock': out_of_stock_variants,
            'low_stock_items': low_stock_items,
            'low_stock_variants': low_stock_items
        },
        'top_selling': top_selling_products,
        'recent_orders': recent_orders,
        'status_counts': status_counts,
        'order_statuses': status_counts
    }


# ==============================================================================
# 3. SALES OVERVIEW CHART DATA GENERATOR
# ==============================================================================

def get_sales_chart_data(period='daily'):
    """
    Aggregates completed recognized revenue and order volume for interactive Chart.js rendering.
    Supports periods: 'daily' (last 30 days), 'weekly' (last 12 weeks),
    'monthly' (last 12 months), 'yearly' (last 5 years).
    Strictly excludes cancelled, returned, refunded, and pending orders.
    """
    now = datetime.utcnow()
    period = (period or 'daily').lower().strip()

    labels = []
    revenues = []
    order_counts = []

    if period == 'daily':
        # Last 30 days
        for i in range(29, -1, -1):
            day_dt = now - timedelta(days=i)
            day_start = datetime(day_dt.year, day_dt.month, day_dt.day, 0, 0, 0)
            day_end = datetime(day_dt.year, day_dt.month, day_dt.day, 23, 59, 59, 999999)

            bucket_orders = Order.query.filter(
                Order.payment_status.in_(['paid', 'collected', 'partially_refunded']),
                ~Order.order_status.in_(['Cancelled', 'Returned']),
                Order.payment_status != 'refunded',
                Order.created_at >= day_start,
                Order.created_at <= day_end
            ).all()
            bucket_rec = [o for o in bucket_orders if is_order_recognized_sale(o)]

            labels.append(day_dt.strftime('%d %b'))
            revenues.append(round(sum(get_order_recognized_revenue(o) for o in bucket_rec), 2))
            order_counts.append(len(bucket_rec))

    elif period == 'weekly':
        # Last 12 weeks
        for i in range(11, -1, -1):
            week_end_dt = now - timedelta(weeks=i)
            # Find Monday of that week
            week_start_dt = week_end_dt - timedelta(days=week_end_dt.weekday())
            w_start = datetime(week_start_dt.year, week_start_dt.month, week_start_dt.day, 0, 0, 0)
            w_end = w_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

            bucket_orders = Order.query.filter(
                Order.payment_status.in_(['paid', 'collected', 'partially_refunded']),
                ~Order.order_status.in_(['Cancelled', 'Returned']),
                Order.payment_status != 'refunded',
                Order.created_at >= w_start,
                Order.created_at <= w_end
            ).all()
            bucket_rec = [o for o in bucket_orders if is_order_recognized_sale(o)]

            labels.append(w_start.strftime('Wk %W (%d %b)'))
            revenues.append(round(sum(get_order_recognized_revenue(o) for o in bucket_rec), 2))
            order_counts.append(len(bucket_rec))

    elif period == 'monthly':
        # Last 12 months
        year = now.year
        month = now.month
        month_list = []
        for _ in range(12):
            month_list.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        month_list.reverse()

        for y, m in month_list:
            m_start = datetime(y, m, 1, 0, 0, 0)
            if m == 12:
                m_end = datetime(y + 1, 1, 1, 0, 0, 0) - timedelta(microseconds=1)
            else:
                m_end = datetime(y, m + 1, 1, 0, 0, 0) - timedelta(microseconds=1)

            bucket_orders = Order.query.filter(
                Order.payment_status.in_(['paid', 'collected', 'partially_refunded']),
                ~Order.order_status.in_(['Cancelled', 'Returned']),
                Order.payment_status != 'refunded',
                Order.created_at >= m_start,
                Order.created_at <= m_end
            ).all()
            bucket_rec = [o for o in bucket_orders if is_order_recognized_sale(o)]

            labels.append(m_start.strftime('%b %Y'))
            revenues.append(round(sum(get_order_recognized_revenue(o) for o in bucket_rec), 2))
            order_counts.append(len(bucket_rec))

    elif period == 'yearly':
        # Last 5 years
        current_year = now.year
        for y in range(current_year - 4, current_year + 1):
            y_start = datetime(y, 1, 1, 0, 0, 0)
            y_end = datetime(y, 12, 31, 23, 59, 59, 999999)

            bucket_orders = Order.query.filter(
                Order.payment_status.in_(['paid', 'collected', 'partially_refunded']),
                ~Order.order_status.in_(['Cancelled', 'Returned']),
                Order.payment_status != 'refunded',
                Order.created_at >= y_start,
                Order.created_at <= y_end
            ).all()
            bucket_rec = [o for o in bucket_orders if is_order_recognized_sale(o)]

            labels.append(str(y))
            revenues.append(round(sum(get_order_recognized_revenue(o) for o in bucket_rec), 2))
            order_counts.append(len(bucket_rec))

    return {
        'period': period,
        'labels': labels,
        'revenues': revenues,
        'revenue': revenues,
        'order_counts': order_counts,
        'orders': order_counts,
        'total_period_revenue': round(sum(revenues), 2),
        'total_period_orders': sum(order_counts)
    }


# ==============================================================================
# 4. COMPREHENSIVE SALES REPORT GENERATOR
# ==============================================================================

def get_sales_report_data(period='this_month', start_date_str=None, end_date_str=None, category_id=None, sort_by='revenue'):
    """
    Aggregates comprehensive financial, product, payment method, and status breakdown
    for the dedicated admin Sales Reports portal and file exports.
    Strictly enforces revenue recognition: excludes cancelled, returned, refunded,
    failed, and pending orders. Reconciles product-level and report-level refund attributions.
    """
    start_dt, end_dt, period_label = resolve_date_range(period, start_date_str, end_date_str)

    # 1. Base Query for Completed/Recognized Orders
    candidates = Order.query.filter(
        Order.created_at >= start_dt,
        Order.created_at <= end_dt,
        Order.payment_status.in_(['paid', 'collected', 'partially_refunded']),
        ~Order.order_status.in_(['Cancelled', 'Returned']),
        Order.payment_status != 'refunded'
    ).all()
    completed_orders = [o for o in candidates if is_order_recognized_sale(o)]
    completed_order_ids = [o.id for o in completed_orders]

    # 2. Refunded / Returned Orders
    refund_candidates = Order.query.filter(
        Order.created_at >= start_dt,
        Order.created_at <= end_dt,
        or_(
            Order.payment_status.in_(['refunded', 'partially_refunded']),
            Order.order_status == 'Returned'
        )
    ).all()

    order_refund_map = {}
    total_refunds = 0.0
    for ro in refund_candidates:
        ref_amt = get_order_refund_amount(ro)
        if ref_amt > 0:
            order_refund_map[ro.id] = ref_amt
            total_refunds += ref_amt

    # 3. Overall Sales Summary
    gross_sales = round(sum(float(o.subtotal or 0.0) for o in completed_orders), 2)
    discount_total = round(sum(float(o.discount_amount or 0.0) for o in completed_orders), 2)
    delivery_fee_total = round(sum(float(o.delivery_fee or 0.0) for o in completed_orders), 2)
    refund_total = round(total_refunds, 2)

    # Net revenue = Gross sales - Discounts + Delivery fees - Refunds
    net_revenue = round(gross_sales - discount_total + delivery_fee_total - refund_total, 2)
    completed_orders_count = len(completed_orders)
    aov = round((net_revenue / completed_orders_count), 2) if completed_orders_count > 0 else 0.0

    # 4. Product-wise Sales Report & Refund Attribution
    product_sales_dict = {}
    if completed_order_ids:
        items = OrderItem.query.filter(OrderItem.order_id.in_(completed_order_ids)).all()
        for it in items:
            p_id = it.product_id or f"unlinked_{it.product_name}"
            if p_id not in product_sales_dict:
                prod = it.product
                cat_name = prod.category.name if (prod and prod.category) else 'General Collection'
                product_sales_dict[p_id] = {
                    'product_id': it.product_id,
                    'name': it.product_name,
                    'sku': prod.sku if prod else 'N/A',
                    'category': cat_name,
                    'units_sold': 0,
                    'gross_sales': 0.0,
                    'discounts': 0.0,
                    'refunds': 0.0,
                    'net_sales': 0.0
                }

            product_sales_dict[p_id]['units_sold'] += it.quantity
            product_sales_dict[p_id]['gross_sales'] += it.total_price

            ord_ref = it.order
            if ord_ref and ord_ref.subtotal and ord_ref.subtotal > 0 and ord_ref.discount_amount and ord_ref.discount_amount > 0:
                item_discount = (it.total_price / ord_ref.subtotal) * ord_ref.discount_amount
                product_sales_dict[p_id]['discounts'] += item_discount

    # Attribute refunds to products
    for ord_id, ref_amt in order_refund_map.items():
        if ref_amt <= 0:
            continue
        ord_items = OrderItem.query.filter_by(order_id=ord_id).all()
        if not ord_items:
            continue
        ord_obj = db.session.get(Order, ord_id)
        ord_subtotal = float(ord_obj.subtotal or 0.0) if ord_obj else 0.0

        for it in ord_items:
            p_id = it.product_id or f"unlinked_{it.product_name}"
            if p_id not in product_sales_dict:
                prod = it.product
                cat_name = prod.category.name if (prod and prod.category) else 'General Collection'
                product_sales_dict[p_id] = {
                    'product_id': it.product_id,
                    'name': it.product_name,
                    'category': cat_name,
                    'sku': prod.sku if prod else 'N/A',
                    'units_sold': 0,
                    'gross_sales': 0.0,
                    'discounts': 0.0,
                    'refunds': 0.0,
                    'net_sales': 0.0
                }
            if ord_subtotal > 0:
                item_refund = (it.total_price / ord_subtotal) * ref_amt
            else:
                item_refund = ref_amt / len(ord_items)
            product_sales_dict[p_id]['refunds'] += item_refund

    # Calculate net sales per product
    product_sales = list(product_sales_dict.values())
    for p in product_sales:
        p['gross_sales'] = round(p['gross_sales'], 2)
        p['gross_revenue'] = p['gross_sales']
        p['discounts'] = round(p['discounts'], 2)
        p['discount_attributed'] = p['discounts']
        p['refunds'] = round(p['refunds'], 2)
        p['net_sales'] = round(p['gross_sales'] - p['discounts'] - p['refunds'], 2)
        p['net_revenue'] = p['net_sales']
        p['avg_realized_price'] = round(p['net_sales'] / p['units_sold'], 2) if p['units_sold'] > 0 else 0.0
        prod_obj = db.session.get(Product, p['product_id']) if isinstance(p['product_id'], int) else None
        p['sku'] = prod_obj.sku if prod_obj else p.get('sku', 'N/A')

    # Sort products
    if sort_by == 'units':
        product_sales.sort(key=lambda x: x['units_sold'], reverse=True)
    elif sort_by == 'name':
        product_sales.sort(key=lambda x: x['name'].lower())
    else:  # default 'revenue'
        product_sales.sort(key=lambda x: x['net_sales'], reverse=True)

    # 5. Payment Method Report
    all_period_orders = Order.query.filter(
        Order.created_at >= start_dt,
        Order.created_at <= end_dt
    ).all()

    payment_method_dict = {
        'razorpay': {
            'method_name': 'Razorpay Online Payment (Cards/UPI/NetBanking)',
            'order_count': 0,
            'total_amount': 0.0,
            'paid_amount': 0.0,
            'pending_amount': 0.0,
            'refunded_amount': 0.0
        },
        'cod': {
            'method_name': 'Cash on Delivery (COD)',
            'order_count': 0,
            'total_amount': 0.0,
            'paid_amount': 0.0,
            'pending_amount': 0.0,
            'refunded_amount': 0.0
        }
    }

    for ord in all_period_orders:
        pm = (ord.payment_method or 'razorpay').lower()
        if pm not in payment_method_dict:
            payment_method_dict[pm] = {
                'method_name': pm.upper(),
                'order_count': 0,
                'total_amount': 0.0,
                'paid_amount': 0.0,
                'pending_amount': 0.0,
                'refunded_amount': 0.0
            }

        rec = payment_method_dict[pm]
        rec['order_count'] += 1
        rec['total_amount'] += ord.total_amount

        if ord.payment_status in ('paid', 'collected'):
            rec['paid_amount'] += ord.total_amount
        elif ord.payment_status == 'refunded':
            rec['refunded_amount'] += ord.total_amount
        else:
            rec['pending_amount'] += ord.total_amount

    payment_method_report = list(payment_method_dict.values())
    for pm in payment_method_report:
        pm['total_amount'] = round(pm['total_amount'], 2)
        pm['paid_amount'] = round(pm['paid_amount'], 2)
        pm['pending_amount'] = round(pm['pending_amount'], 2)
        pm['refunded_amount'] = round(pm['refunded_amount'], 2)
        pm['name'] = pm['method_name']
        pm['orders_count'] = pm['order_count']
        pm['total_collected'] = pm['paid_amount']
        pm['percentage'] = round((pm['paid_amount'] / net_revenue * 100.0), 1) if net_revenue > 0 else 0.0

    # 6. Order Status Report
    order_status_report = []
    total_period_orders_count = len(all_period_orders)

    for st in SUPPORTED_ORDER_STATUSES:
        matching = [o for o in all_period_orders if o.order_status == st]
        val = sum(o.total_amount for o in matching)
        pct = round((len(matching) / total_period_orders_count * 100.0), 1) if total_period_orders_count > 0 else 0.0
        order_status_report.append({
            'status': st,
            'count': len(matching),
            'value': round(val, 2),
            'total_value': round(val, 2),
            'percentage': pct
        })

    return {
        'period': period,
        'period_label': period_label,
        'start_date': start_dt,
        'end_date': end_dt,
        'start_date_str': start_dt.strftime('%Y-%m-%d'),
        'end_date_str': end_dt.strftime('%Y-%m-%d'),
        'generated_at': datetime.utcnow().strftime('%d %b %Y, %I:%M %p UTC'),
        'sort_by': sort_by,
        'summary': {
            'gross_sales': round(gross_sales, 2),
            'discounts': round(discount_total, 2),
            'delivery_fees': round(delivery_fee_total, 2),
            'refunds': round(refund_total, 2),
            'net_revenue': round(net_revenue, 2),
            'orders_count': completed_orders_count,
            'average_order_value': round(aov, 2),
            'aov': round(aov, 2)
        },
        'product_sales': product_sales,
        'product_breakdown': product_sales,
        'payment_methods': payment_method_report,
        'payment_breakdown': payment_method_report,
        'order_statuses': order_status_report,
        'status_breakdown': order_status_report
    }


# ==============================================================================
# 5. CSV EXPORT GENERATOR
# ==============================================================================

def generate_sales_csv(report_data):
    """
    Renders comprehensive CSV export matching current reporting filter and accounting standards.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header / Meta
    writer.writerow(["COSTUME STORE — FINANCIAL SALES & REVENUE REPORT"])
    writer.writerow(["Reporting Period", report_data.get('period_label', '')])
    writer.writerow(["Date Range", f"{report_data.get('start_date_str')} to {report_data.get('end_date_str')}"])
    writer.writerow(["Generated At", report_data.get('generated_at', '')])
    writer.writerow([])

    # 1. Summary
    s = report_data.get('summary', {})
    writer.writerow(["--- SALES SUMMARY ---"])
    writer.writerow(["Metric", "Amount (INR)"])
    writer.writerow(["Gross Sales", f"{s.get('gross_sales', 0.0):.2f}"])
    writer.writerow(["Discounts Given", f"{s.get('discounts', 0.0):.2f}"])
    writer.writerow(["Delivery Fees Collected", f"{s.get('delivery_fees', 0.0):.2f}"])
    writer.writerow(["Refunds & Returns", f"{s.get('refunds', 0.0):.2f}"])
    writer.writerow(["Net Realized Revenue", f"{s.get('net_revenue', 0.0):.2f}"])
    writer.writerow(["Completed Paid Orders", s.get('orders_count', 0)])
    writer.writerow(["Average Order Value (AOV)", f"{s.get('average_order_value', 0.0):.2f}"])
    writer.writerow([])

    # 2. Product-wise sales
    writer.writerow(["--- PRODUCT-WISE SALES BREAKDOWN ---"])
    writer.writerow(["Product Name", "Category", "Units Sold", "Gross Sales", "Discounts", "Refunds", "Net Sales"])
    for p in report_data.get('product_sales', []):
        writer.writerow([
            p['name'],
            p['category'],
            p['units_sold'],
            f"{p['gross_sales']:.2f}",
            f"{p['discounts']:.2f}",
            f"{p['refunds']:.2f}",
            f"{p['net_sales']:.2f}"
        ])
    writer.writerow([])

    # 3. Payment Methods
    writer.writerow(["--- PAYMENT METHODS BREAKDOWN ---"])
    writer.writerow(["Payment Gateway / Method", "Order Count", "Total Value", "Paid/Collected", "Pending", "Refunded"])
    for pm in report_data.get('payment_methods', []):
        writer.writerow([
            pm['method_name'],
            pm['order_count'],
            f"{pm['total_amount']:.2f}",
            f"{pm['paid_amount']:.2f}",
            f"{pm['pending_amount']:.2f}",
            f"{pm['refunded_amount']:.2f}"
        ])
    writer.writerow([])

    # 4. Order Statuses
    writer.writerow(["--- ORDER STATUS DISTRIBUTION ---"])
    writer.writerow(["Order Status", "Order Count", "Total Value (INR)", "Percentage"])
    for st in report_data.get('order_statuses', []):
        writer.writerow([
            st['status'],
            st['count'],
            f"{st['value']:.2f}",
            f"{st['percentage']}%"
        ])

    return output.getvalue().encode('utf-8-sig')


# ==============================================================================
# 6. EXCEL (.XLSX) EXPORT GENERATOR
# ==============================================================================

def generate_sales_excel(report_data):
    """
    Renders valid, multi-worksheet .xlsx workbook via openpyxl with formatted headers,
    numeric cells, currency styles, and totals rows.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active

    # Brand Colors
    HEADER_FILL = PatternFill(start_color="5B1427", end_color="5B1427", fill_type="solid")
    HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    TITLE_FONT = Font(name="Calibri", size=14, bold=True, color="5B1427")
    BOLD_FONT = Font(name="Calibri", size=11, bold=True)
    REGULAR_FONT = Font(name="Calibri", size=11)
    TOTAL_FILL = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='E5E7EB'),
        right=Side(style='thin', color='E5E7EB'),
        top=Side(style='thin', color='E5E7EB'),
        bottom=Side(style='thin', color='E5E7EB')
    )

    # -------------------------------------------------------------
    # Sheet 1: Sales Summary
    # -------------------------------------------------------------
    ws1 = wb.create_sheet(title="Executive Summary")
    ws1.views.sheetView[0].showGridLines = True

    ws1.cell(row=1, column=1, value="COSTUME STORE — EXECUTIVE SALES SUMMARY").font = TITLE_FONT
    ws1.cell(row=2, column=1, value=f"Period: {report_data.get('period_label')} ({report_data.get('start_date_str')} to {report_data.get('end_date_str')})").font = REGULAR_FONT
    ws1.cell(row=3, column=1, value=f"Generated At: {report_data.get('generated_at')}").font = REGULAR_FONT

    s = report_data.get('summary', {})
    summary_rows = [
        ("Gross Sales (Product Subtotals)", s.get('gross_sales', 0.0), "currency"),
        ("Coupons & Promotional Discounts", s.get('discounts', 0.0), "currency"),
        ("Delivery Fees Collected", s.get('delivery_fees', 0.0), "currency"),
        ("Refunds & Customer Returns", s.get('refunds', 0.0), "currency"),
        ("Net Realized Revenue", s.get('net_revenue', 0.0), "currency"),
        ("Completed Paid Orders Count", s.get('orders_count', 0), "integer"),
        ("Average Order Value (AOV)", s.get('average_order_value', 0.0), "currency")
    ]

    ws1.cell(row=5, column=1, value="Sales & Financial Metric").font = HEADER_FONT
    ws1.cell(row=5, column=1).fill = HEADER_FILL
    ws1.cell(row=5, column=2, value="Value (INR)").font = HEADER_FONT
    ws1.cell(row=5, column=2).fill = HEADER_FILL

    for idx, (label, val, ftype) in enumerate(summary_rows, start=6):
        c1 = ws1.cell(row=idx, column=1, value=label)
        c2 = ws1.cell(row=idx, column=2, value=val)
        c1.font = BOLD_FONT if 'Net' in label else REGULAR_FONT
        c2.font = BOLD_FONT if 'Net' in label else REGULAR_FONT
        c1.border = thin_border
        c2.border = thin_border
        if ftype == "currency":
            c2.number_format = '"₹"#,##0.00'
        else:
            c2.number_format = '#,##0'

    ws1.column_dimensions['A'].width = 38
    ws1.column_dimensions['B'].width = 24

    # -------------------------------------------------------------
    # Sheet 2: Product-wise Sales
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="Product Sales")
    ws2.views.sheetView[0].showGridLines = True

    p_headers = ["Product Name", "Category", "Units Sold", "Gross Sales", "Discounts", "Refunds", "Net Sales"]
    for col_idx, h in enumerate(p_headers, start=1):
        cell = ws2.cell(row=1, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center' if col_idx == 3 else 'left')

    row_num = 2
    for p in report_data.get('product_sales', []):
        c1 = ws2.cell(row=row_num, column=1, value=p['name'])
        c2 = ws2.cell(row=row_num, column=2, value=p['category'])
        c3 = ws2.cell(row=row_num, column=3, value=p['units_sold'])
        c4 = ws2.cell(row=row_num, column=4, value=p['gross_sales'])
        c5 = ws2.cell(row=row_num, column=5, value=p['discounts'])
        c6 = ws2.cell(row=row_num, column=6, value=p['refunds'])
        c7 = ws2.cell(row=row_num, column=7, value=p['net_sales'])

        for c in (c1, c2, c3, c4, c5, c6, c7):
            c.font = REGULAR_FONT
            c.border = thin_border

        c3.number_format = '#,##0'
        c4.number_format = '"₹"#,##0.00'
        c5.number_format = '"₹"#,##0.00'
        c6.number_format = '"₹"#,##0.00'
        c7.number_format = '"₹"#,##0.00'
        row_num += 1

    # Total Row for Products
    if report_data.get('product_sales'):
        t_label = ws2.cell(row=row_num, column=1, value="TOTAL")
        t_label.font = BOLD_FONT
        t_label.fill = TOTAL_FILL
        t_label.border = thin_border

        for ci in range(2, 8):
            cell = ws2.cell(row=row_num, column=ci)
            cell.font = BOLD_FONT
            cell.fill = TOTAL_FILL
            cell.border = thin_border

        ws2.cell(row=row_num, column=3, value=f"=SUM(C2:C{row_num-1})").number_format = '#,##0'
        ws2.cell(row=row_num, column=4, value=f"=SUM(D2:D{row_num-1})").number_format = '"₹"#,##0.00'
        ws2.cell(row=row_num, column=5, value=f"=SUM(E2:E{row_num-1})").number_format = '"₹"#,##0.00'
        ws2.cell(row=row_num, column=6, value=f"=SUM(F2:F{row_num-1})").number_format = '"₹"#,##0.00'
        ws2.cell(row=row_num, column=7, value=f"=SUM(G2:G{row_num-1})").number_format = '"₹"#,##0.00'

    ws2.column_dimensions['A'].width = 44
    ws2.column_dimensions['B'].width = 24
    ws2.column_dimensions['C'].width = 14
    ws2.column_dimensions['D'].width = 16
    ws2.column_dimensions['E'].width = 16
    ws2.column_dimensions['F'].width = 16
    ws2.column_dimensions['G'].width = 18

    # -------------------------------------------------------------
    # Sheet 3: Payment Methods
    # -------------------------------------------------------------
    ws3 = wb.create_sheet(title="Payment Methods")
    ws3.views.sheetView[0].showGridLines = True

    pm_headers = ["Payment Gateway / Method", "Orders Count", "Total Value", "Paid/Collected", "Pending", "Refunded"]
    for col_idx, h in enumerate(pm_headers, start=1):
        cell = ws3.cell(row=1, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL

    row_num = 2
    for pm in report_data.get('payment_methods', []):
        c1 = ws3.cell(row=row_num, column=1, value=pm['method_name'])
        c2 = ws3.cell(row=row_num, column=2, value=pm['order_count'])
        c3 = ws3.cell(row=row_num, column=3, value=pm['total_amount'])
        c4 = ws3.cell(row=row_num, column=4, value=pm['paid_amount'])
        c5 = ws3.cell(row=row_num, column=5, value=pm['pending_amount'])
        c6 = ws3.cell(row=row_num, column=6, value=pm['refunded_amount'])

        for c in (c1, c2, c3, c4, c5, c6):
            c.font = REGULAR_FONT
            c.border = thin_border

        c2.number_format = '#,##0'
        c3.number_format = '"₹"#,##0.00'
        c4.number_format = '"₹"#,##0.00'
        c5.number_format = '"₹"#,##0.00'
        c6.number_format = '"₹"#,##0.00'
        row_num += 1

    ws3.column_dimensions['A'].width = 40
    ws3.column_dimensions['B'].width = 16
    ws3.column_dimensions['C'].width = 18
    ws3.column_dimensions['D'].width = 18
    ws3.column_dimensions['E'].width = 18
    ws3.column_dimensions['F'].width = 18

    # -------------------------------------------------------------
    # Sheet 4: Order Statuses
    # -------------------------------------------------------------
    ws4 = wb.create_sheet(title="Order Statuses")
    ws4.views.sheetView[0].showGridLines = True

    st_headers = ["Order Status", "Order Count", "Total Value (INR)", "Share (%)"]
    for col_idx, h in enumerate(st_headers, start=1):
        cell = ws4.cell(row=1, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL

    row_num = 2
    for st in report_data.get('order_statuses', []):
        c1 = ws4.cell(row=row_num, column=1, value=st['status'])
        c2 = ws4.cell(row=row_num, column=2, value=st['count'])
        c3 = ws4.cell(row=row_num, column=3, value=st['value'])
        c4 = ws4.cell(row=row_num, column=4, value=f"{st['percentage']}%")

        for c in (c1, c2, c3, c4):
            c.font = REGULAR_FONT
            c.border = thin_border

        c2.number_format = '#,##0'
        c3.number_format = '"₹"#,##0.00'
        row_num += 1

    ws4.column_dimensions['A'].width = 24
    ws4.column_dimensions['B'].width = 16
    ws4.column_dimensions['C'].width = 22
    ws4.column_dimensions['D'].width = 14

    # Remove temporary default sheet
    wb.remove(default_sheet)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream.getvalue()


# ==============================================================================
# 7. PDF EXPORT GENERATOR (REPORTLAB)
# ==============================================================================

class NumberedCanvas:
    """Canvas wrapper that tracks page numbers and prints total page count in footer."""
    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas
        self._canvas_cls = canvas.Canvas
        self.args = args
        self.kwargs = kwargs
        self.pages = []

    def __call__(self, *args, **kwargs):
        inst = self._canvas_cls(*args, **kwargs)
        orig_showPage = inst.showPage
        orig_save = inst.save

        def my_showPage():
            inst._pageNumber += 1
            orig_showPage()

        def my_save():
            num_pages = inst._pageNumber - 1
            for page in inst._saved_page_states:
                inst.__dict__.update(page)
                inst.drawRightString(200, 20, f"Page {inst._pageNumber} of {num_pages}")
            orig_save()

        inst.showPage = my_showPage
        return inst


def generate_sales_pdf(report_data):
    """
    Renders professional PDF report document via ReportLab with executive header,
    summary cards, product sales table, payment breakdown, and page numbers.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    stream = io.BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    PRIMARY = colors.HexColor('#5B1427')
    ACCENT = colors.HexColor('#C5A059')
    BG_LIGHT = colors.HexColor('#F9FAFB')
    BORDER_COLOR = colors.HexColor('#E5E7EB')
    TEXT_DARK = colors.HexColor('#1F2937')

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=PRIMARY,
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#6B7280'),
        spaceAfter=14
    )
    section_heading = ParagraphStyle(
        'SecHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=PRIMARY,
        spaceBefore=12,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=TEXT_DARK
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    cell_header = ParagraphStyle(
        'CellHeader',
        parent=cell_style,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )

    story = []

    # Title & Header
    header_html = "<b><font size='16'>COSTUME STORE</font></b> — Executive Sales & Revenue Report"
    story.append(Paragraph(header_html, title_style))
    sub_text = f"<b>Reporting Period:</b> {report_data.get('period_label')} ({report_data.get('start_date_str')} to {report_data.get('end_date_str')}) &nbsp;|&nbsp; <b>Generated:</b> {report_data.get('generated_at')}"
    story.append(Paragraph(sub_text, subtitle_style))
    story.append(Spacer(1, 4))

    # 1. Sales Summary Table
    story.append(Paragraph("1. Executive Financial Summary", section_heading))
    s = report_data.get('summary', {})
    sum_data = [
        [Paragraph("Financial Metric", cell_header), Paragraph("Amount / Count", cell_header)],
        [Paragraph("Gross Merchandise Value (Subtotal)", cell_style), Paragraph(f"₹{s.get('gross_sales', 0.0):,.2f}", cell_style)],
        [Paragraph("Coupons & Promotional Discounts", cell_style), Paragraph(f"₹{s.get('discounts', 0.0):,.2f}", cell_style)],
        [Paragraph("Shipping & Delivery Fees Collected", cell_style), Paragraph(f"₹{s.get('delivery_fees', 0.0):,.2f}", cell_style)],
        [Paragraph("Customer Refunds & Returned Orders", cell_style), Paragraph(f"₹{s.get('refunds', 0.0):,.2f}", cell_style)],
        [Paragraph("<b>Net Realized Sales Revenue</b>", cell_bold), Paragraph(f"<b>₹{s.get('net_revenue', 0.0):,.2f}</b>", cell_bold)],
        [Paragraph("Completed Paid Orders Count", cell_style), Paragraph(f"{s.get('orders_count', 0):,}", cell_style)],
        [Paragraph("Average Order Value (AOV)", cell_style), Paragraph(f"₹{s.get('average_order_value', 0.0):,.2f}", cell_style)],
    ]
    sum_table = Table(sum_data, colWidths=[340, 180])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0, 5), (-1, 5), BG_LIGHT),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 10))

    # 2. Product-wise Sales
    story.append(Paragraph("2. Product-wise Performance Breakdown", section_heading))
    p_rows = [
        [
            Paragraph("Product Name", cell_header),
            Paragraph("Category", cell_header),
            Paragraph("Units", cell_header),
            Paragraph("Gross (₹)", cell_header),
            Paragraph("Refunds (₹)", cell_header),
            Paragraph("Net Sales (₹)", cell_header)
        ]
    ]

    p_list = report_data.get('product_sales', [])
    if p_list:
        for p in p_list[:25]:  # Top 25 products in PDF for clean pagination
            p_rows.append([
                Paragraph(p['name'], cell_style),
                Paragraph(p['category'], cell_style),
                Paragraph(str(p['units_sold']), cell_style),
                Paragraph(f"{p['gross_sales']:,.2f}", cell_style),
                Paragraph(f"{p.get('refunds', 0.0):,.2f}", cell_style),
                Paragraph(f"{p['net_sales']:,.2f}", cell_bold)
            ])
    else:
        p_rows.append([Paragraph("No completed product sales recorded in selected period.", cell_style), "", "", "", "", ""])

    p_table = Table(p_rows, colWidths=[175, 110, 45, 65, 60, 65])
    p_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(p_table)
    story.append(Spacer(1, 10))

    # 3. Payment Methods & Order Status Breakdown
    story.append(Paragraph("3. Payment Gateways & Order Status Distribution", section_heading))
    pm_data = [
        [
            Paragraph("Payment Method", cell_header),
            Paragraph("Orders", cell_header),
            Paragraph("Paid/Collected (₹)", cell_header),
            Paragraph("Pending (₹)", cell_header)
        ]
    ]
    for pm in report_data.get('payment_methods', []):
        pm_data.append([
            Paragraph(pm['method_name'], cell_style),
            Paragraph(str(pm['order_count']), cell_style),
            Paragraph(f"₹{pm['paid_amount']:,.2f}", cell_style),
            Paragraph(f"₹{pm['pending_amount']:,.2f}", cell_style)
        ])

    pm_table = Table(pm_data, colWidths=[230, 70, 110, 110])
    pm_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(pm_table)
    story.append(Spacer(1, 8))

    # Order Status summary
    st_data = [
        [
            Paragraph("Order Status", cell_header),
            Paragraph("Count", cell_header),
            Paragraph("Total Value (₹)", cell_header),
            Paragraph("Share (%)", cell_header)
        ]
    ]
    for ost in report_data.get('order_statuses', []):
        st_data.append([
            Paragraph(ost['status'], cell_style),
            Paragraph(str(ost['count']), cell_style),
            Paragraph(f"₹{ost['value']:,.2f}", cell_style),
            Paragraph(f"{ost['percentage']}%", cell_style)
        ])
    st_table = Table(st_data, colWidths=[200, 90, 130, 100])
    st_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(st_table)

    # Footer decorator
    def add_page_decorations(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#6B7280'))
        footer_text = f"COSTUME STORE E-Commerce Platform — Strictly Confidential Management Report — Generated {report_data.get('generated_at')}"
        canvas.drawString(36, 20, footer_text)
        canvas.drawRightString(A4[0] - 36, 20, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
    stream.seek(0)
    return stream.getvalue()
