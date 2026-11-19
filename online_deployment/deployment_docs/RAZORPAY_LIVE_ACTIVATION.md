# Costume Store — Razorpay Live Mode Activation Manual

The Costume Store application supports both **Test Mode** (for rehearsals and development) and **Live Mode** (for accepting real UPI, card, and netbanking payments in Indian Rupees).

By default, the application runs strictly in **Test Mode**. Real money cannot be charged until you complete the explicit activation steps detailed below.

---

## 1. Safety Architecture

- **No Real Payments During Preparation**: The preparation tasks use Test Mode exclusively.
- **HMAC-SHA256 Signature Verification**: All payments require cryptographic signature verification on the server before an order is placed.
- **Amount & Currency Validation**: All amounts are verified on the backend in integer paise (`₹1.00 = 100 paise`).
- **Webhook Reconciliation**: Server verifies Razorpay webhook signatures on `/webhook/razorpay` to handle payment notifications asynchronously.

---

## 2. Prerequisites for Live Activation

Before enabling Live Mode on your public store:
1. Complete your business KYC in the [Razorpay Dashboard](https://dashboard.razorpay.com/).
2. Submit your bank account details for automated settlements.
3. Verify your store policies (Terms, Privacy, Refund & Shipping Policy) are live on your website footer.

---

## 3. Step-by-Step Live Activation Procedure

### Step 1: Generate Live API Keys
1. Log in to the [Razorpay Dashboard](https://dashboard.razorpay.com/).
2. Toggle the switch at the top-left from **Test Mode** to **Live Mode**.
3. Navigate to **Settings** -> **API Keys**.
4. Click **Generate Live Key**.
5. Copy:
   - **Live Key ID** (starts with `rzp_live_...`)
   - **Live Key Secret** (keep this secret; do not share or commit to Git)

### Step 2: Configure Live Webhook
1. In the Razorpay Dashboard (under Live Mode), navigate to **Settings** -> **Webhooks**.
2. Click **Add New Webhook**.
3. Enter:
   - **Webhook URL**: `https://<your-custom-domain>/webhook/razorpay`
   - **Secret**: *(Generate a random 32-character secret string)*
   - **Active Events**: Check `payment.captured`, `payment.failed`, `order.paid`.
4. Save the Webhook.

### Step 3: Update Cloud Environment Variables
In your cloud deployment dashboard (e.g. Render Dashboard -> Web Service -> Environment):
Update the following variables:

```env
RAZORPAY_MODE=live
RAZORPAY_KEY_ID=rzp_live_YOUR_LIVE_KEY_ID
RAZORPAY_KEY_SECRET=YOUR_LIVE_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET=YOUR_LIVE_WEBHOOK_SECRET
```

### Step 4: Restart Web Service
Trigger a redeploy or restart on Render to load the updated environment variables.

---

## 4. Verification & First Transaction Test

1. Visit your live store website (`https://<your-domain>/`).
2. Add a product variant to your shopping bag.
3. Proceed to `/checkout`.
4. Select **Razorpay (Credit / Debit Card / UPI / NetBanking)**.
5. In the Razorpay Checkout modal, perform a small test transaction (e.g., ₹10 or ₹50) using UPI or a live card.
6. Verify:
   - The payment succeeds and redirects to order confirmation.
   - The order status in `/admin/orders` updates to `Confirmed` and `paid`.
   - Inventory decrements by exactly 1.
   - The transaction appears under **Transactions** in your Razorpay Live Dashboard.
7. Perform a refund test from `/admin/orders` if desired.

---

## 5. Deactivation (Rollback to Test Mode)

To revert to Test Mode at any time:
1. Change `RAZORPAY_MODE=test` in your deployment environment variables.
2. Replace `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` with your test credentials (`rzp_test_...`).
3. Restart the service.
