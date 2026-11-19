"""
COSTUME STORE — Database Seeding Script for Authentic Indian Traditional Catalogue
Populates categories, subcategories, 26 authentic Indian ethnic products,
variants, images, coupons, and store settings.
Fully idempotent: safe to execute repeatedly without duplicating records.
"""

import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from datetime import datetime, timedelta
from app import app
from models import (
    db, Category, Product, ProductImage, ProductVariant,
    Coupon, StoreSetting
)

def seed_database():
    with app.app_context():
        db.create_all()

        # ----------------------------------------------------------------------
        # 1. STORE SETTINGS
        # ----------------------------------------------------------------------
        settings = {
            'store_name': 'COSTUME STORE',
            'tagline': 'Authentic Indian Traditional Clothing & Festive Costumes',
            'contact_email': 'support@costumestore.com',
            'contact_phone': '+91 98765 43210',
            'address': '45 Heritage Boulevard, Fashion District, Bengaluru, Karnataka 560001',
            'currency_symbol': '₹',
            'delivery_charge': '99.0',
            'free_delivery_threshold': '1499.0',
            'cod_enabled': 'true',
            'return_policy': '7-day easy returns & exchanges for unworn items with tags intact.'
        }
        for k, v in settings.items():
            setting = StoreSetting.query.filter_by(key=k).first()
            if not setting:
                db.session.add(StoreSetting(key=k, value=v))
            else:
                setting.value = v
        db.session.commit()

        # ----------------------------------------------------------------------
        # 2. CATEGORIES & SUBCATEGORIES
        # ----------------------------------------------------------------------
        category_data = [
            {
                'name': "Women's Collection",
                'slug': 'women',
                'description': 'Handcrafted pure Kanchipuram and Banarasi silk sarees, bridal lehengas, Anarkalis, salwar suits, and traditional half sarees.',
                'image_url': '/static/images/categories/women-ethnic.jpg',
                'subs': [
                    {'name': 'Kanchipuram Silk Sarees', 'slug': 'kanchipuram-sarees'},
                    {'name': 'Banarasi Silk Sarees', 'slug': 'banarasi-sarees'},
                    {'name': 'Cotton & Handloom Sarees', 'slug': 'cotton-sarees'},
                    {'name': 'Designer & Party Sarees', 'slug': 'designer-sarees'},
                    {'name': 'Bridal Lehengas', 'slug': 'bridal-lehengas'},
                    {'name': 'Anarkali Suits', 'slug': 'anarkali-suits'},
                    {'name': 'Salwar Kameez & Churidar', 'slug': 'salwar-kameez'},
                    {'name': 'Pavadai Dhavani (Half Sarees)', 'slug': 'half-sarees'}
                ]
            },
            {
                'name': "Men's Collection",
                'slug': 'men',
                'description': 'Regal hand-embroidered sherwanis, pure silk kurta pajamas, South Indian veshti and shirt sets, dhoti sets, and Nehru jackets.',
                'image_url': '/static/images/categories/men-ethnic.jpg',
                'subs': [
                    {'name': 'Royal Sherwanis', 'slug': 'mens-sherwanis'},
                    {'name': 'Kurta Pajama Sets', 'slug': 'kurta-pajama'},
                    {'name': 'Veshti & Shirt Sets', 'slug': 'veshti-shirt'},
                    {'name': 'Dhoti & Angavastram', 'slug': 'dhoti-sets'},
                    {'name': 'Nehru Jackets & Bandis', 'slug': 'nehru-jackets'},
                    {'name': 'Indo-Western & Bandhgalas', 'slug': 'indo-western'}
                ]
            },
            {
                'name': "Kids' Collection",
                'slug': 'kids',
                'description': 'Adorable traditional Pattu Pavadais for girls, festive lehenga cholis, boys kurta pajamas, and kids dhoti sets for weddings.',
                'image_url': '/static/images/categories/kids-ethnic.jpg',
                'subs': [
                    {'name': "Girls' Pattu Pavadai", 'slug': 'girls-pattu-pavadai'},
                    {'name': "Girls' Lehenga Choli", 'slug': 'girls-lehengas'},
                    {'name': "Boys' Kurta Pajama", 'slug': 'boys-kurta'},
                    {'name': "Kids' Dhoti Sets", 'slug': 'kids-dhoti'},
                    {'name': "Kids' Traditional Wedding Wear", 'slug': 'kids-wedding'}
                ]
            },
            {
                'name': "Festival & Dance",
                'slug': 'festival',
                'description': 'Special traditional costumes for Diwali, Pongal, Onam, Navratri Garba Chaniya Cholis, and classical Indian dance costumes.',
                'image_url': '/static/images/categories/festival-dance.jpg',
                'subs': [
                    {'name': 'Navratri Chaniya Choli', 'slug': 'navratri-chaniya-choli'},
                    {'name': 'Onam Kasavu Sarees', 'slug': 'onam-kasavu'},
                    {'name': 'Diwali & Pongal Outfits', 'slug': 'diwali-pongal'},
                    {'name': 'Bharatanatyam Dance Costumes', 'slug': 'bharatanatyam-dance'},
                    {'name': 'Kathak & Folk Dance Costumes', 'slug': 'folk-dance'}
                ]
            }
        ]

        cat_lookup = {}
        visible_slugs = {'women', 'men', 'kids', 'festival'}
        for c_idx, cdata in enumerate(category_data):
            cat = Category.query.filter_by(slug=cdata['slug']).first()
            if not cat:
                cat = Category(
                    name=cdata['name'],
                    slug=cdata['slug'],
                    description=cdata['description'],
                    image_url=cdata['image_url'],
                    display_order=c_idx,
                    is_active=True,
                    is_visible_on_storefront=True
                )
                db.session.add(cat)
                db.session.flush()
            else:
                cat.name = cdata['name']
                cat.description = cdata['description']
                cat.image_url = cdata['image_url']
                cat.display_order = c_idx
                cat.is_active = True
                cat.is_visible_on_storefront = True
            cat_lookup[cat.slug] = cat

            for s_idx, sdata in enumerate(cdata['subs']):
                sub = Category.query.filter_by(slug=sdata['slug']).first()
                if not sub:
                    sub = Category(
                        name=sdata['name'],
                        slug=sdata['slug'],
                        image_url=cdata['image_url'],
                        parent_id=cat.id,
                        display_order=s_idx,
                        is_active=True,
                        is_visible_on_storefront=True
                    )
                    db.session.add(sub)
                    db.session.flush()
                else:
                    sub.name = sdata['name']
                    sub.parent_id = cat.id
                    sub.display_order = s_idx
                    sub.is_active = True
                    sub.is_visible_on_storefront = True
                cat_lookup[sub.slug] = sub

        # Dormant categories available in admin for future use (hidden from public storefront)
        dormant_categories = [
            {'name': 'Cosplay & Theatrical', 'slug': 'cosplay-theatre', 'description': 'Theatrical and cosplay costumes for performance.'},
            {'name': 'Fancy Dress & Party', 'slug': 'fancy-dress', 'description': 'Party costumes and fancy dress collections.'},
            {'name': 'Accessories & Props', 'slug': 'accessories', 'description': 'Costume accessories, turbans, jewelry, and props.'},
            {'name': 'Special Occasion Costumes', 'slug': 'special-costumes', 'description': 'Specialized cultural and stage costumes.'}
        ]
        for d_idx, ddata in enumerate(dormant_categories, start=10):
            dcat = Category.query.filter_by(slug=ddata['slug']).first()
            if not dcat:
                dcat = Category(
                    name=ddata['name'],
                    slug=ddata['slug'],
                    description=ddata['description'],
                    display_order=d_idx,
                    is_active=True,
                    is_visible_on_storefront=False
                )
                db.session.add(dcat)
            else:
                dcat.is_visible_on_storefront = False

        # Ensure non-catalogue legacy categories are marked hidden from customer storefront
        all_existing_cats = Category.query.all()
        for ec in all_existing_cats:
            if ec.parent_id is None:
                if ec.slug not in visible_slugs:
                    ec.is_visible_on_storefront = False
            else:
                if not ec.parent or ec.parent.slug not in visible_slugs:
                    ec.is_visible_on_storefront = False

        db.session.commit()

        # ----------------------------------------------------------------------
        # 3. AUTHENTIC INDIAN TRADITIONAL PRODUCTS (26 INTENDED PRODUCTS)
        # ----------------------------------------------------------------------
        products_data = [
            # === WOMEN'S COLLECTION ===
            {
                'name': 'Kanchipuram Pure Silk Saree with Real Zari Border',
                'slug': 'kanchipuram-pure-silk-saree',
                'cat': 'women',
                'subcat': 'kanchipuram-sarees',
                'brand': 'Kanchi Weaves Heritage',
                'base_price': 8499.0,
                'discount_price': 6999.0,
                'sku': 'IND-WOM-KANCHI-001',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Masterfully handwoven pure mulberry silk saree originating from Kanchipuram, Tamil Nadu. Handcrafted in regal peacock blue and teal silk with authentic golden zari temple motifs, opulent pallu, and includes an unstitched matching silk blouse piece.',
                'details': 'Fabric: 100% Pure Mulberry Silk | Weave: Handloom Kanchipuram Korvai | Length: 6.3m (including 0.8m blouse piece) | Care: Dry clean only | Occasion: Weddings, Temple Ceremonies, Festive Rituals',
                'image': '/static/images/products/women/kanchipuram-silk-saree-01.jpg',
                'variants': [
                    {'size': 'Free Size', 'colour': 'Peacock Blue & Gold', 'colour_code': '#004953', 'stock': 18},
                    {'size': 'Free Size', 'colour': 'Teal Green & Gold', 'colour_code': '#00563F', 'stock': 12},
                    {'size': 'Free Size', 'colour': 'Royal Blue & Gold', 'colour_code': '#4169E1', 'stock': 15}
                ]
            },
            {
                'name': 'Banarasi Zari Woven Katan Silk Saree',
                'slug': 'banarasi-zari-katan-silk-saree',
                'cat': 'women',
                'subcat': 'banarasi-sarees',
                'brand': 'Varanasi Royal Loom',
                'base_price': 6499.0,
                'discount_price': 5299.0,
                'sku': 'IND-WOM-BANARAS-002',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': False,
                'description': 'Opulent Varanasi handloom Katan silk saree in rich crimson ruby red, showcasing intricate floral jaal patterns, kalga motifs, and elaborate kadwa golden zari borders. Drapes with fluid royal grace.',
                'details': 'Fabric: Pure Katan Silk | Weave: Banarasi Kadwa Brocade | Length: 5.5m Saree + 0.8m Blouse | Care: Dry Clean Only | Occasion: Grand Receptions, Diwali, Family Celebrations',
                'image': '/static/images/products/women/banarasi-saree-01.jpg',
                'variants': [
                    {'size': 'Free Size', 'colour': 'Crimson Red & Gold', 'colour_code': '#9B111E', 'stock': 20},
                    {'size': 'Free Size', 'colour': 'Ruby Red & Zari', 'colour_code': '#E0115F', 'stock': 14},
                    {'size': 'Free Size', 'colour': 'Royal Maroon', 'colour_code': '#800000', 'stock': 10}
                ]
            },
            {
                'name': 'Pure Handloom Cotton Saree (Sambalpuri Ikat Weave)',
                'slug': 'handloom-chanderi-cotton-saree',
                'cat': 'women',
                'subcat': 'cotton-sarees',
                'brand': 'Chanderi Artisans',
                'base_price': 2999.0,
                'discount_price': 2299.0,
                'sku': 'IND-WOM-CHANDERI-003',
                'is_featured': False,
                'is_bestseller': False,
                'is_trending': False,
                'description': 'Authentic handloom pure cotton saree hand-spun by traditional master weavers in the renowned Sambalpuri tie-dye (Bandhakala) technique. Features breathable soft textured cotton in deep indigo blue with artisanal geometric border and contrast pallu.',
                'details': 'Fabric: 100% Pure Handloom Cotton | Weave: Sambalpuri Tie-Dye (Ikat) | Length: 6.2m | Texture: Breathable & Lightweight | Origin: Odisha | Care: Gentle Hand Wash in Cold Water',
                'image': '/static/images/products/women/cotton-saree-01.jpg',
                'variants': [
                    {'size': 'Free Size', 'colour': 'Indigo Blue & Crimson', 'colour_code': '#2B3D52', 'stock': 22},
                    {'size': 'Free Size', 'colour': 'Midnight Blue & Red', 'colour_code': '#191970', 'stock': 16},
                    {'size': 'Free Size', 'colour': 'Deep Navy Blue', 'colour_code': '#000080', 'stock': 18}
                ]
            },
            {
                'name': 'Embroidered Designer Georgette Saree',
                'slug': 'embroidered-designer-georgette-saree',
                'cat': 'women',
                'subcat': 'designer-sarees',
                'brand': 'Sanskriti Couture',
                'base_price': 4499.0,
                'discount_price': 3699.0,
                'sku': 'IND-WOM-DESIGNER-004',
                'is_featured': True,
                'is_bestseller': False,
                'is_trending': True,
                'description': 'Contemporary designer georgette saree featuring intricate thread embroidery, cut-work scalloped borders, and delicate sequin embellishments. Comes with a designer heavy worked blouse fabric.',
                'details': 'Fabric: Premium Flowing Faux Georgette | Work: Dori & Sequin Embroidery | Blouse: Heavy Satin Silk | Care: Dry Clean Only',
                'image': '/static/images/products/women/designer-saree-01.jpg',
                'variants': [
                    {'size': 'Free Size', 'colour': 'Pastel Peach', 'colour_code': '#FFDAB9', 'stock': 15},
                    {'size': 'Free Size', 'colour': 'Mint Green', 'colour_code': '#98FF98', 'stock': 12},
                    {'size': 'Free Size', 'colour': 'Royal Blue', 'colour_code': '#4169E1', 'stock': 14}
                ]
            },
            {
                'name': 'Embroidered Designer Bridal Lehenga Choli Ensemble',
                'slug': 'royal-bridal-velvet-lehenga',
                'cat': 'women',
                'subcat': 'bridal-lehengas',
                'brand': 'Varanasi Royal Loom',
                'base_price': 18999.0,
                'discount_price': 14999.0,
                'sku': 'IND-WOM-BRIDAL-005',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Breathtaking contemporary Indian bridal lehenga ensemble featuring handcrafted gold bullion and sequin embroidery across an ethereal pastel sage green flared skirt, embellished designer choli, and ornate matching bridal dupatta.',
                'details': 'Fabric: Premium Silk & Embroidered Organza Net | Flair: Voluminous Multi-Kalidar Cut | Work: Zari & Hand-Sequinned Embroidery | Dupatta: 2.5m Hand-Embroidered Borders | Care: Professional Dry Clean Only',
                'image': '/static/images/products/women/bridal-lehenga-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Pastel Sage Green & Gold', 'colour_code': '#B2AC88', 'stock': 8},
                    {'size': 'M', 'colour': 'Pastel Sage Green & Gold', 'colour_code': '#B2AC88', 'stock': 10},
                    {'size': 'L', 'colour': 'Mint Green & Gold', 'colour_code': '#98FF98', 'stock': 12},
                    {'size': 'XL', 'colour': 'Emerald Sage', 'colour_code': '#50C878', 'stock': 6}
                ]
            },
            {
                'name': 'Floor-Length Embroidered Anarkali Suit',
                'slug': 'floor-length-anarkali-suit',
                'cat': 'women',
                'subcat': 'anarkali-suits',
                'brand': 'Sanskriti Couture',
                'base_price': 5499.0,
                'discount_price': 4299.0,
                'sku': 'IND-WOM-ANARKALI-006',
                'is_featured': False,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Sweeping 56-kalidar floor-length Anarkali suit with embroidered sweetheart yoke, full sleeves, Santoon churidar pants, and a scalloped georgette dupatta.',
                'details': 'Fabric: Pure Chiffon Georgette & Shantoon | Length: 56 inches | Lining: Pure Cotton Voile | Wash: Dry clean recommended | Occasion: Eid, Family Gatherings, Parties',
                'image': '/static/images/products/women/anarkali-suit-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Royal Navy', 'colour_code': '#000080', 'stock': 10},
                    {'size': 'M', 'colour': 'Royal Navy', 'colour_code': '#000080', 'stock': 14},
                    {'size': 'L', 'colour': 'Bottle Green', 'colour_code': '#004225', 'stock': 12},
                    {'size': 'XL', 'colour': 'Wine Red', 'colour_code': '#722F37', 'stock': 8}
                ]
            },
            {
                'name': 'Traditional Punjabi Salwar Kameez Suit',
                'slug': 'traditional-punjabi-salwar-kameez',
                'cat': 'women',
                'subcat': 'salwar-kameez',
                'brand': 'Sanskriti Couture',
                'base_price': 3299.0,
                'discount_price': 2599.0,
                'sku': 'IND-WOM-SALWAR-007',
                'is_featured': False,
                'is_bestseller': False,
                'is_trending': False,
                'description': 'Authentic Punjabi patiala salwar suit stitched with Phulkari-inspired embroidery across the neckline and cuffs. Features voluminous pleated patiala bottoms and matching chanderi dupatta.',
                'details': 'Fabric: Glace Cotton Top with Cotton Patiala | Dupatta: Nazneen Chiffon | Fit: Regular Traditional Fit | Care: Hand Wash Cold',
                'image': '/static/images/products/women/salwar-kameez-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Marigold & Red', 'colour_code': '#FFAA00', 'stock': 14},
                    {'size': 'M', 'colour': 'Marigold & Red', 'colour_code': '#FFAA00', 'stock': 18},
                    {'size': 'L', 'colour': 'Deep Purple', 'colour_code': '#4B0082', 'stock': 12},
                    {'size': 'XL', 'colour': 'Emerald Green', 'colour_code': '#00563F', 'stock': 10}
                ]
            },
            {
                'name': 'Chanderi Silk Churidar Suit with Dupatta',
                'slug': 'chanderi-silk-churidar-suit',
                'cat': 'women',
                'subcat': 'salwar-kameez',
                'brand': 'Chanderi Artisans',
                'base_price': 3799.0,
                'discount_price': 2999.0,
                'sku': 'IND-WOM-CHURIDAR-008',
                'is_featured': False,
                'is_bestseller': False,
                'is_trending': False,
                'description': 'Tailored straight-cut Chanderi silk kurta paired with gather-fit cotton lycra churidar trousers and a dual-shade woven dupatta with zari pattu borders.',
                'details': 'Top: Chanderi Silk with Cotton Lining | Bottom: Stretch Churidar | Dupatta: 2.2m Chanderi Pattu | Care: Dry Clean',
                'image': '/static/images/products/women/churidar-suit-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Coral Pink', 'colour_code': '#F88379', 'stock': 12},
                    {'size': 'M', 'colour': 'Coral Pink', 'colour_code': '#F88379', 'stock': 15},
                    {'size': 'L', 'colour': 'Teal Blue', 'colour_code': '#008080', 'stock': 14},
                    {'size': 'XL', 'colour': 'Golden Beige', 'colour_code': '#F5F5DC', 'stock': 9}
                ]
            },
            {
                'name': 'Traditional Pavadai Dhavani (South Indian Half Saree)',
                'slug': 'traditional-pavadai-dhavani-half-saree',
                'cat': 'women',
                'subcat': 'half-sarees',
                'brand': 'Kanchi Weaves Heritage',
                'base_price': 4999.0,
                'discount_price': 3999.0,
                'sku': 'IND-WOM-HALFSAREE-009',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Classic South Indian Dhavani ensemble consisting of a pleated pure art silk skirt (lehenga/pavadai), embroidered blouse choli, and sheer dhavani dupatta drape with temple borders.',
                'details': 'Fabric: Art Kanchipuram Silk | Set Includes: Pavadai Skirt, Stitched Blouse, and Dhavani Voile | Occasion: Ritu Kala Samskara, Temple Festivals, Pongal',
                'image': '/static/images/products/women/pavadai-dhavani-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Green & Maroon', 'colour_code': '#006400', 'stock': 12},
                    {'size': 'M', 'colour': 'Green & Maroon', 'colour_code': '#006400', 'stock': 16},
                    {'size': 'L', 'colour': 'Mustard & Red', 'colour_code': '#D4AF37', 'stock': 14},
                    {'size': 'XL', 'colour': 'Peacock Blue & Pink', 'colour_code': '#005F73', 'stock': 8}
                ]
            },

            # === MEN'S COLLECTION ===
            {
                'name': 'Royal Hand-Embroidered Groom Wedding Sherwani Set',
                'slug': 'royal-embroidered-groom-sherwani',
                'cat': 'men',
                'subcat': 'mens-sherwanis',
                'brand': 'Maharaja Heritage',
                'base_price': 14999.0,
                'discount_price': 11999.0,
                'sku': 'IND-MEN-SHERWANI-010',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Imperial royal wedding sherwani tailored in raw silk with champagne and antique gold threadwork, mandarin collar with zardozi embroidery, pearl trim, matching churidar trousers, and ceremonial stole.',
                'details': 'Fabric: Banarasi Raw Silk & Brocade | Lining: Cotton Silk | Set: Sherwani Coat, Inner Kurta, Churidar, Stole | Care: Dry Clean Only | Occasion: Weddings, Baraat, Royal Receptions',
                'image': '/static/images/products/men/mens-sherwani-01.jpg',
                'variants': [
                    {'size': '38', 'colour': 'Champagne Gold & Cream', 'colour_code': '#F7E7CE', 'stock': 10},
                    {'size': '40', 'colour': 'Champagne Gold & Cream', 'colour_code': '#F7E7CE', 'stock': 15},
                    {'size': '42', 'colour': 'Ivory Gold', 'colour_code': '#FFFFF0', 'stock': 12},
                    {'size': '44', 'colour': 'Warm Beige & Zari', 'colour_code': '#F5F5DC', 'stock': 8}
                ]
            },
            {
                'name': 'Traditional Silk Kurta and Pyjama Set',
                'slug': 'pure-silk-kurta-pajama-set',
                'cat': 'men',
                'subcat': 'kurta-pajama',
                'brand': 'Maharaja Heritage',
                'base_price': 3499.0,
                'discount_price': 2799.0,
                'sku': 'IND-MEN-KURTA-011',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': False,
                'description': 'Classic Indian men\'s tailored dupion silk kurta featuring mandarin collar, buttoned placket, and deep rust maroon textured weave. Accompanied by comfortable traditional drawstring pyjama trousers.',
                'details': 'Fabric: Dupion Art Silk | Kurta Length: Knee-Length Regular Fit | Pockets: 2 Side Slit Pockets | Set: Kurta + Drawstring Pyjama | Care: Gentle Hand Wash or Dry Clean',
                'image': '/static/images/products/men/kurta-pajama-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Rust Maroon', 'colour_code': '#800000', 'stock': 14},
                    {'size': 'M', 'colour': 'Rust Maroon', 'colour_code': '#800000', 'stock': 18},
                    {'size': 'L', 'colour': 'Crimson Red', 'colour_code': '#990000', 'stock': 16},
                    {'size': 'XL', 'colour': 'Wine Silk', 'colour_code': '#722F37', 'stock': 12},
                    {'size': 'XXL', 'colour': 'Rust Maroon', 'colour_code': '#800000', 'stock': 8}
                ]
            },
            {
                'name': 'South Indian Pure Silk Veshti and Shirt Set',
                'slug': 'south-indian-silk-veshti-shirt-set',
                'cat': 'men',
                'subcat': 'veshti-shirt',
                'brand': 'Dakshin Splendour',
                'base_price': 3999.0,
                'discount_price': 3199.0,
                'sku': 'IND-MEN-VESHTI-012',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Authentic South Indian wedding set including pure art silk stitched formal shirt and traditional 8-muzham dhoti (veshti) with woven pure golden zari border.',
                'details': 'Fabric: Art Mulberry Silk | Set: Half/Full Sleeve Shirt + 3.6m Veshti + Matching Angavastram | Occasion: South Indian Weddings, Pongal, Temple Feasts',
                'image': '/static/images/products/men/veshti-shirt-set-01.jpg',
                'variants': [
                    {'size': '38', 'colour': 'Pure Cream & Gold', 'colour_code': '#FFFDD0', 'stock': 14},
                    {'size': '40', 'colour': 'Pure Cream & Gold', 'colour_code': '#FFFDD0', 'stock': 20},
                    {'size': '42', 'colour': 'Off-White & Gold', 'colour_code': '#FAF0E6', 'stock': 16},
                    {'size': '44', 'colour': 'Pure Cream & Gold', 'colour_code': '#FFFDD0', 'stock': 10}
                ]
            },
            {
                'name': 'Handloom Cotton Dhoti and Angavastram Set',
                'slug': 'handloom-cotton-dhoti-angavastram',
                'cat': 'men',
                'subcat': 'dhoti-sets',
                'brand': 'Dakshin Splendour',
                'base_price': 1799.0,
                'discount_price': 1399.0,
                'sku': 'IND-MEN-DHOTI-013',
                'is_featured': False,
                'is_bestseller': False,
                'is_trending': False,
                'description': 'Lightweight 100% fine combed cotton traditional dhoti paired with an angavastram shoulder drape. Finished with traditional red and gold Ganga-Jamuna woven borders.',
                'details': 'Fabric: 100% Pure Combed Cotton | Length: 4.0m Dhoti + 2.0m Angavastram | Border: Traditional Temple Kasavu | Wash: Gentle Hand Wash',
                'image': '/static/images/products/men/dhoti-shirt-01.jpg',
                'variants': [
                    {'size': 'Free Size', 'colour': 'White with Red Border', 'colour_code': '#FFFFFF', 'stock': 25},
                    {'size': 'Free Size', 'colour': 'White with Gold Zari', 'colour_code': '#FAF0E6', 'stock': 20},
                    {'size': 'Free Size', 'colour': 'White with Green Border', 'colour_code': '#F5FFFA', 'stock': 15}
                ]
            },
            {
                'name': 'Raw Silk Handcrafted Nehru Jacket (Bandi)',
                'slug': 'raw-silk-nehru-jacket',
                'cat': 'men',
                'subcat': 'nehru-jackets',
                'brand': 'Maharaja Heritage',
                'base_price': 2799.0,
                'discount_price': 2199.0,
                'sku': 'IND-MEN-NEHRU-014',
                'is_featured': True,
                'is_bestseller': False,
                'is_trending': True,
                'description': 'Classic sleeveless Nehru jacket tailored in structured raw silk with mandarin collar, five metallic front buttons, chest welt pocket, and vented hemline. Layers smartly over kurtas.',
                'details': 'Fabric: Raw Matka Silk | Lining: Poly Satin | Fit: Slim Tailored Fit | Pockets: 1 Chest Welt + 2 Lower Pockets | Care: Dry Clean Only',
                'image': '/static/images/products/men/nehru-jacket-01.jpg',
                'variants': [
                    {'size': '38', 'colour': 'Emerald Green', 'colour_code': '#00563F', 'stock': 12},
                    {'size': '40', 'colour': 'Emerald Green', 'colour_code': '#00563F', 'stock': 15},
                    {'size': '42', 'colour': 'Royal Saffron', 'colour_code': '#FF9933', 'stock': 14},
                    {'size': '44', 'colour': 'Midnight Black', 'colour_code': '#000000', 'stock': 10}
                ]
            },
            {
                'name': 'Royal Jodhpuri Bandhgala Wedding Suit',
                'slug': 'royal-jodhpuri-bandhgala-suit',
                'cat': 'men',
                'subcat': 'indo-western',
                'brand': 'Maharaja Heritage',
                'base_price': 11999.0,
                'discount_price': 9499.0,
                'sku': 'IND-MEN-JODHPURI-015',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Iconic Indian royal Bandhgala coat tailored in structured Terry Rayon with velvet-accented mandarin collar, crest metal buttons, and matching tailored trousers.',
                'details': 'Fabric: Premium Suiting Blend | Style: Single Breasted Closed Collar | Set: Bandhgala Coat + Formal Trousers | Care: Dry Clean Only',
                'image': '/static/images/products/men/jodhpuri-bandhgala-01.jpg',
                'variants': [
                    {'size': '38', 'colour': 'Jet Black & Gold', 'colour_code': '#1B1B1B', 'stock': 10},
                    {'size': '40', 'colour': 'Jet Black & Gold', 'colour_code': '#1B1B1B', 'stock': 14},
                    {'size': '42', 'colour': 'Regal Navy Blue', 'colour_code': '#000080', 'stock': 12},
                    {'size': '44', 'colour': 'Charcoal Grey', 'colour_code': '#36454F', 'stock': 8}
                ]
            },
            {
                'name': 'Modern Indo-Western Asymmetric Kurta Outfit',
                'slug': 'modern-indo-western-kurta-outfit',
                'cat': 'men',
                'subcat': 'indo-western',
                'brand': 'Sanskriti Couture',
                'base_price': 5299.0,
                'discount_price': 4199.0,
                'sku': 'IND-MEN-INDOWEST-016',
                'is_featured': False,
                'is_bestseller': False,
                'is_trending': True,
                'description': 'Contemporary Indo-Western overlapping cowl kurta with attached drape jacket and tapered modern dhoti trousers. Merges runway style with ethnic dignity.',
                'details': 'Fabric: Heavy Moss Crepe & Art Silk | Drape: Integrated Pleated Cowl | Bottom: Pre-pleated Stretch Dhoti Pants | Care: Dry Clean',
                'image': '/static/images/products/men/indo-western-men-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Slate Grey', 'colour_code': '#708090', 'stock': 12},
                    {'size': 'M', 'colour': 'Slate Grey', 'colour_code': '#708090', 'stock': 16},
                    {'size': 'L', 'colour': 'Forest Green', 'colour_code': '#228B22', 'stock': 14},
                    {'size': 'XL', 'colour': 'Ivory Cream', 'colour_code': '#FFFFF0', 'stock': 8}
                ]
            },

            # === KIDS' COLLECTION ===
            {
                'name': "Girls' Traditional Kanchipuram Pattu Pavadai",
                'slug': 'girls-kanchipuram-pattu-pavadai',
                'cat': 'kids',
                'subcat': 'girls-pattu-pavadai',
                'brand': 'Bal Gokul Kids',
                'base_price': 3499.0,
                'discount_price': 2799.0,
                'sku': 'IND-KID-PAVADAI-017',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Pure silk handwoven Pattu Pavadai and stitched puff-sleeve top for young girls. Adorned with traditional peacock motifs, heavy zari border, and soft cotton inner lining for sensitive skin.',
                'details': 'Fabric: 100% Pure Silk with Soft Cotton Lining | Closure: Back Zipper & Drawstring Skirt | Age: 2 to 10 Years | Wash: Dry Clean',
                'image': '/static/images/products/kids/girls-pattu-pavadai-01.jpg',
                'variants': [
                    {'size': '2-3 Yrs', 'colour': 'Magenta & Gold', 'colour_code': '#FF00FF', 'stock': 12},
                    {'size': '4-5 Yrs', 'colour': 'Magenta & Gold', 'colour_code': '#FF00FF', 'stock': 15},
                    {'size': '6-7 Yrs', 'colour': 'Bottle Green & Red', 'colour_code': '#006400', 'stock': 14},
                    {'size': '8-10 Yrs', 'colour': 'Mango Yellow & Pink', 'colour_code': '#FFB703', 'stock': 10}
                ]
            },
            {
                'name': "Girls' Festive Silk Lehenga Choli Set",
                'slug': 'girls-festive-silk-lehenga-choli',
                'cat': 'kids',
                'subcat': 'girls-lehengas',
                'brand': 'Bal Gokul Kids',
                'base_price': 2999.0,
                'discount_price': 2399.0,
                'sku': 'IND-KID-LEHENGA-018',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': False,
                'description': 'Bright festive flared lehenga skirt with gold foil print, mirror-work choli blouse, and light net dupatta with beaded tassels. Ideal for wedding functions and Diwali.',
                'details': 'Fabric: Jacquard Art Silk with Net Dupatta | Lining: Skin-friendly breathable cotton | Waist: Elasticated Back with Latkan Drawstring',
                'image': '/static/images/products/kids/girls-lehenga-choli-01.jpg',
                'variants': [
                    {'size': '3-4 Yrs', 'colour': 'Radiant Pink', 'colour_code': '#FF69B4', 'stock': 10},
                    {'size': '5-6 Yrs', 'colour': 'Radiant Pink', 'colour_code': '#FF69B4', 'stock': 14},
                    {'size': '7-8 Yrs', 'colour': 'Bright Peach', 'colour_code': '#FFCBA4', 'stock': 12},
                    {'size': '9-10 Yrs', 'colour': 'Peacock Blue', 'colour_code': '#005F73', 'stock': 8}
                ]
            },
            {
                'name': "Boys' Jacquard Kurta Pajama with Nehru Jacket",
                'slug': 'boys-jacquard-kurta-pajama-jacket',
                'cat': 'kids',
                'subcat': 'boys-kurta',
                'brand': 'Bal Gokul Kids',
                'base_price': 2499.0,
                'discount_price': 1899.0,
                'sku': 'IND-KID-KURTA-019',
                'is_featured': False,
                'is_bestseller': True,
                'is_trending': True,
                'description': '3-piece ethnic set for boys comprising an all-over floral jacquard Nehru waistcoat, cotton silk kurta, and elasticated pajama bottoms. Classy, comfortable, and celebratory.',
                'details': 'Set: 1 Kurta + 1 Pajama + 1 Jacket | Fabric: Cotton Blend with Jacquard Brocade | Care: Gentle Machine Wash / Dry Clean',
                'image': '/static/images/products/kids/boys-kurta-pajama-01.jpg',
                'variants': [
                    {'size': '2-3 Yrs', 'colour': 'Royal Mustard & Maroon', 'colour_code': '#FFC000', 'stock': 12},
                    {'size': '4-5 Yrs', 'colour': 'Royal Mustard & Maroon', 'colour_code': '#FFC000', 'stock': 16},
                    {'size': '6-7 Yrs', 'colour': 'Turquoise Blue', 'colour_code': '#40E0D0', 'stock': 14},
                    {'size': '8-10 Yrs', 'colour': 'Pearl White & Gold', 'colour_code': '#F5F5F5', 'stock': 10}
                ]
            },
            {
                'name': "Kids' Traditional South Indian Pattu Veshti (Dhoti)",
                'slug': 'kids-traditional-dhoti-kurta-set',
                'cat': 'kids',
                'subcat': 'kids-dhoti',
                'brand': 'Dakshin Splendour',
                'base_price': 1999.0,
                'discount_price': 1499.0,
                'sku': 'IND-KID-DHOTI-020',
                'is_featured': False,
                'is_bestseller': False,
                'is_trending': False,
                'description': 'Authentic South Indian festive pattu veshti (dhoti) crafted in pure white silk-cotton with traditional golden kasavu zari border. Tailored for comfort and cultural grace during temple ceremonies, Upanayanam, Pongal, and family weddings.',
                'details': 'Fabric: Pure Silk-Cotton Blend | Border: Golden Kasavu Zari Border | Age: 2 to 10 Years | Fit: Traditional Draped Fit | Occasion: Temple Visits, Pongal, Onam, Family Functions',
                'image': '/static/images/products/kids/kids-dhoti-set-01.jpg',
                'variants': [
                    {'size': '2-3 Yrs', 'colour': 'Classic White & Gold Zari', 'colour_code': '#FFFFFF', 'stock': 12},
                    {'size': '4-5 Yrs', 'colour': 'Classic White & Gold Zari', 'colour_code': '#FFFFFF', 'stock': 18},
                    {'size': '6-7 Yrs', 'colour': 'Cream & Gold Zari', 'colour_code': '#FFFDD0', 'stock': 15},
                    {'size': '8-10 Yrs', 'colour': 'Classic White & Gold Zari', 'colour_code': '#FFFFFF', 'stock': 10}
                ]
            },
            {
                'name': "Kids' Royal Wedding Sherwani Suit",
                'slug': 'kids-royal-wedding-sherwani',
                'cat': 'kids',
                'subcat': 'kids-wedding',
                'brand': 'Bal Gokul Kids',
                'base_price': 3999.0,
                'discount_price': 3199.0,
                'sku': 'IND-KID-WEDDING-021',
                'is_featured': True,
                'is_bestseller': False,
                'is_trending': True,
                'description': 'Miniature royal wedding sherwani crafted for young boys. Features ornate zardozi embroidery over textured brocade, paired with churidar trousers and a contrast festive stole.',
                'details': 'Set: Sherwani Coat + Pajama + Dupatta | Fabric: Brocade Art Silk with Cotton Voile Lining | Age: 3 to 12 Years | Care: Dry Clean Only',
                'image': '/static/images/products/kids/kids-wedding-wear-01.jpg',
                'variants': [
                    {'size': '3-4 Yrs', 'colour': 'Navy Blue & Gold', 'colour_code': '#000080', 'stock': 10},
                    {'size': '5-6 Yrs', 'colour': 'Navy Blue & Gold', 'colour_code': '#000080', 'stock': 14},
                    {'size': '7-8 Yrs', 'colour': 'Royal Maroon & Gold', 'colour_code': '#800000', 'stock': 12},
                    {'size': '9-10 Yrs', 'colour': 'Cream & Antique Gold', 'colour_code': '#FFFDD0', 'stock': 8}
                ]
            },

            # === FESTIVAL & SPECIAL OCCASIONS ===
            {
                'name': 'Navratri Mirror-Work Chaniya Choli Set',
                'slug': 'navratri-mirror-work-chaniya-choli',
                'cat': 'festival',
                'subcat': 'navratri-chaniya-choli',
                'brand': 'Utsav Traditions',
                'base_price': 4999.0,
                'discount_price': 3999.0,
                'sku': 'IND-FEST-NAVRATRI-022',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Spectacular 12-meter circular flare Dandiya Garba chaniya choli embellished with authentic Abhala mirror-work, colorful pom-poms, and handcrafted kutch embroidery.',
                'details': 'Fabric: Heavy Pure Cotton | Work: Real Mirror & Gamthi Work | Set: Chaniya Skirt, Choli Blouse, Bandhani Dupatta | Occasion: Navratri Dandiya Raas, Garba Nights',
                'image': '/static/images/products/festival/navratri-chaniya-choli-01.jpg',
                'variants': [
                    {'size': 'Free Size', 'colour': 'Multicolour on Black', 'colour_code': '#1B1B1B', 'stock': 20},
                    {'size': 'Free Size', 'colour': 'Yellow & Royal Blue', 'colour_code': '#FFD700', 'stock': 15},
                    {'size': 'Free Size', 'colour': 'Crimson Red & Orange', 'colour_code': '#DC143C', 'stock': 18}
                ]
            },
            {
                'name': 'Kerala Traditional Onam Kasavu Saree (Set Mundu)',
                'slug': 'kerala-onam-kasavu-saree',
                'cat': 'festival',
                'subcat': 'onam-kasavu',
                'brand': 'Dakshin Splendour',
                'base_price': 2499.0,
                'discount_price': 1999.0,
                'sku': 'IND-FEST-KASAVU-023',
                'is_featured': True,
                'is_bestseller': False,
                'is_trending': True,
                'description': 'Auspicious Kerala Kasavu Set Mundu handloomed in unbleached organic cotton with broad 3-inch golden zari kasavu borders. The definitive traditional attire for Onam and Vishu.',
                'details': 'Fabric: 100% Pure Organic Cotton | Zari: Traditional Muringa Leaf & Temple Borders | Includes: 2-piece Set Mundu + Blouse Fabric | Wash: Cold Hand Wash',
                'image': '/static/images/products/festival/onam-kasavu-saree-01.jpg',
                'variants': [
                    {'size': 'Free Size', 'colour': 'Golden Zari Border', 'colour_code': '#FFFDD0', 'stock': 25},
                    {'size': 'Free Size', 'colour': 'Temple Green Zari Border', 'colour_code': '#FFFDD0', 'stock': 15},
                    {'size': 'Free Size', 'colour': 'Peacock Temple Zari Border', 'colour_code': '#FFFDD0', 'stock': 18}
                ]
            },
            {
                'name': 'Classical Bharatanatyam Dance Silk Costume',
                'slug': 'classical-bharatanatyam-dance-costume',
                'cat': 'festival',
                'subcat': 'bharatanatyam-dance',
                'brand': 'Natya Shastra Attire',
                'base_price': 5999.0,
                'discount_price': 4799.0,
                'sku': 'IND-FEST-BHARATA-024',
                'is_featured': True,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Professional 3-piece Bharatanatyam dance costume tailored in authentic Dharmavaram art silk with expanding fan pleats, blouse, back cover, and waist belt with golden zari temple borders.',
                'details': 'Fabric: Stiff Woven Dharmavaram Art Silk | Style: Fan Front Traditional Dance Dress | Set: Pyjama with Fan, Choli Blouse, Pallu Drape | Occasion: Arangetram, Stage Performances, Competitions',
                'image': '/static/images/products/festival/bharatanatyam-costume-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Temple Maroon & Mustard', 'colour_code': '#800000', 'stock': 10},
                    {'size': 'M', 'colour': 'Temple Maroon & Mustard', 'colour_code': '#800000', 'stock': 15},
                    {'size': 'L', 'colour': 'Peacock Blue & Orange', 'colour_code': '#0077B6', 'stock': 12},
                    {'size': 'XL', 'colour': 'Golden Yellow & Red', 'colour_code': '#FFB703', 'stock': 8}
                ]
            },
            {
                'name': 'Diwali & Pongal Festive Silk Kurta Pajama with Stole',
                'slug': 'diwali-pongal-festive-silk-kurta-set',
                'cat': 'festival',
                'subcat': 'diwali-pongal',
                'brand': 'Maharaja Heritage',
                'base_price': 3199.0,
                'discount_price': 2499.0,
                'sku': 'IND-FEST-DIWALI-025',
                'is_featured': False,
                'is_bestseller': True,
                'is_trending': True,
                'description': 'Celebratory silk kurta set tailored for Diwali pooja, Pongal gatherings, and festive family dinners. Comes with matching silk churidar and woven zari jacquard stole.',
                'details': 'Fabric: Pure Tussar Silk Blend | Includes: Kurta, Churidar Pajama, Brocade Stole | Wash: Gentle Hand Wash',
                'image': '/static/images/products/festival/diwali-festive-wear-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Deep Saffron', 'colour_code': '#FF9933', 'stock': 12},
                    {'size': 'M', 'colour': 'Deep Saffron', 'colour_code': '#FF9933', 'stock': 18},
                    {'size': 'L', 'colour': 'Royal Wine', 'colour_code': '#722F37', 'stock': 15},
                    {'size': 'XL', 'colour': 'Forest Green', 'colour_code': '#228B22', 'stock': 12},
                    {'size': 'XXL', 'colour': 'Deep Saffron', 'colour_code': '#FF9933', 'stock': 6}
                ]
            },
            {
                'name': 'Kathak & Classical Folk Dance Costume',
                'slug': 'kathak-classical-folk-dance-costume',
                'cat': 'festival',
                'subcat': 'folk-dance',
                'brand': 'Natya Shastra Attire',
                'base_price': 5499.0,
                'discount_price': 4399.0,
                'sku': 'IND-FEST-KATHAK-026',
                'is_featured': False,
                'is_bestseller': False,
                'is_trending': False,
                'description': 'Traditional Kathak classical dance costume featuring an expansive flared anarkali frock with circular gher for chakkar spins, churidar pants, velvet waist jacket, and sheer dupatta.',
                'details': 'Fabric: Heavy Flowing Satin & Chiffon | Gher: Complete 360-degree spin flare | Set: Anarkali Angrakha, Churidar, Dupatta | Occasion: Kathak Recitals, Indian Folk Dance',
                'image': '/static/images/products/festival/folk-dance-costume-01.jpg',
                'variants': [
                    {'size': 'S', 'colour': 'Crimson & Gold', 'colour_code': '#990000', 'stock': 10},
                    {'size': 'M', 'colour': 'Crimson & Gold', 'colour_code': '#990000', 'stock': 14},
                    {'size': 'L', 'colour': 'Emerald Green & Gold', 'colour_code': '#00563F', 'stock': 12},
                    {'size': 'XL', 'colour': 'Crimson & Gold', 'colour_code': '#990000', 'stock': 8}
                ]
            }
        ]

        # Deactivate any legacy/obsolete products not in the 26 authentic items
        new_slugs = {item['slug'] for item in products_data}
        for p in Product.query.all():
            if p.slug not in new_slugs:
                p.is_active = False
        db.session.commit()

        # Seed products idempotently
        for p_data in products_data:
            cat = cat_lookup.get(p_data['cat'])
            subcat = cat_lookup.get(p_data['subcat'])

            prod = Product.query.filter_by(slug=p_data['slug']).first()
            if not prod:
                prod = Product(
                    name=p_data['name'],
                    slug=p_data['slug'],
                    description=p_data['description'],
                    details=p_data['details'],
                    category_id=cat.id if cat else 1,
                    subcategory_id=subcat.id if subcat else None,
                    brand=p_data['brand'],
                    base_price=p_data['base_price'],
                    discount_price=p_data['discount_price'],
                    sku=p_data['sku'],
                    is_featured=p_data['is_featured'],
                    is_bestseller=p_data['is_bestseller'],
                    is_trending=p_data['is_trending'],
                    is_active=True
                )
                db.session.add(prod)
                db.session.flush()
            else:
                prod.name = p_data['name']
                prod.description = p_data['description']
                prod.details = p_data['details']
                prod.category_id = cat.id if cat else prod.category_id
                prod.subcategory_id = subcat.id if subcat else prod.subcategory_id
                prod.brand = p_data['brand']
                prod.base_price = p_data['base_price']
                prod.discount_price = p_data['discount_price']
                prod.is_featured = p_data['is_featured']
                prod.is_bestseller = p_data['is_bestseller']
                prod.is_trending = p_data['is_trending']
                prod.is_active = True

            # Product Image: ensure primary image is configured
            img = ProductImage.query.filter_by(product_id=prod.id, image_url=p_data['image']).first()
            if not img:
                ProductImage.query.filter_by(product_id=prod.id).delete()
                img = ProductImage(
                    product_id=prod.id,
                    image_url=p_data['image'],
                    is_primary=True,
                    display_order=0
                )
                db.session.add(img)
            else:
                img.is_primary = True

            # Product Variants: add or update without duplicating
            for v_data in p_data['variants']:
                v_sku = f"{p_data['sku']}-{v_data['size'].replace(' ', '')}-{v_data['colour'][:3].upper()}"
                variant = ProductVariant.query.filter_by(sku=v_sku).first()
                if not variant:
                    variant = ProductVariant.query.filter_by(product_id=prod.id, size=v_data['size'], colour=v_data['colour']).first()
                if not variant:
                    variant = ProductVariant(
                        product_id=prod.id,
                        size=v_data['size'],
                        colour=v_data['colour'],
                        colour_code=v_data['colour_code'],
                        sku=v_sku,
                        stock_quantity=v_data['stock'],
                        additional_price=0.0,
                        is_active=True
                    )
                    db.session.add(variant)
                else:
                    variant.size = v_data['size']
                    variant.colour = v_data['colour']
                    variant.colour_code = v_data['colour_code']
                    variant.stock_quantity = v_data['stock']
                    variant.sku = v_sku
                    variant.is_active = True



        db.session.commit()

        # ----------------------------------------------------------------------
        # 4. PROMOTIONAL COUPONS
        # ----------------------------------------------------------------------
        coupons = [
            {'code': 'WELCOME10', 'discount_type': 'percentage', 'discount_value': 10.0, 'min_purchase': 0.0, 'max_discount': 500.0},
            {'code': 'TRADITIONAL10', 'discount_type': 'percentage', 'discount_value': 10.0, 'min_purchase': 1000.0, 'max_discount': 500.0},
            {'code': 'FESTIVE20', 'discount_type': 'percentage', 'discount_value': 20.0, 'min_purchase': 2500.0, 'max_discount': 1000.0},
            {'code': 'FLAT300', 'discount_type': 'fixed', 'discount_value': 300.0, 'min_purchase': 1999.0, 'max_discount': None}
        ]
        for cp in coupons:
            c = Coupon.query.filter_by(code=cp['code']).first()
            if not c:
                db.session.add(Coupon(
                    code=cp['code'],
                    discount_type=cp['discount_type'],
                    discount_value=cp['discount_value'],
                    min_purchase=cp['min_purchase'],
                    max_discount=cp['max_discount'],
                    valid_from=datetime.utcnow() - timedelta(days=1),
                    valid_until=datetime.utcnow() + timedelta(days=365),
                    usage_limit=1000,
                    times_used=0,
                    is_active=True
                ))
            else:
                c.discount_type = cp['discount_type']
                c.discount_value = cp['discount_value']
                c.min_purchase = cp['min_purchase']
                c.max_discount = cp['max_discount']
                c.is_active = True
        db.session.commit()

        active_count = Product.query.filter_by(is_active=True).count()
        print(f"Successfully seeded/verified {active_count} authentic Indian traditional products (Idempotent)!")
        return active_count

if __name__ == '__main__':
    seed_database()
