/**
 * COSTUME STORE - Interactive JavaScript Helpers
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Auto-dismiss flash messages after 5 seconds
  const flashAlerts = document.querySelectorAll('.alert');
  flashAlerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });

  // 2. Mobile Menu Toggle
  const mobileToggle = document.getElementById('mobileMenuToggle');
  const mobileDrawer = document.getElementById('mobileDrawer');
  const drawerOverlay = document.getElementById('drawerOverlay');

  if (mobileToggle && mobileDrawer) {
    mobileToggle.addEventListener('click', function () {
      mobileDrawer.classList.toggle('open');
      if (drawerOverlay) drawerOverlay.classList.toggle('open');
    });

    if (drawerOverlay) {
      drawerOverlay.addEventListener('click', function () {
        mobileDrawer.classList.remove('open');
        drawerOverlay.classList.remove('open');
      });
    }
  }

  // 3. Wishlist AJAX Toggle
  const wishlistButtons = document.querySelectorAll('.wishlist-toggle');
  wishlistButtons.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const productId = btn.getAttribute('data-product-id');
      if (!productId) return;

      fetch(`/wishlist/toggle/${productId}`, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/json'
        }
      })
      .then(res => {
        if (res.status === 401) {
          window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
          return null;
        }
        return res.json();
      })
      .then(data => {
        if (!data) return;
        if (data.success) {
          if (data.added) {
            btn.classList.add('active');
            btn.innerHTML = '<i class="fas fa-heart"></i>';
          } else {
            btn.classList.remove('active');
            btn.innerHTML = '<i class="far fa-heart"></i>';
          }
          // Update navbar wishlist count badge
          const badge = document.querySelector('.wishlist-count-badge');
          if (badge) {
            badge.textContent = data.wishlist_count;
            badge.style.display = data.wishlist_count > 0 ? 'flex' : 'none';
          }
        }
      })
      .catch(err => console.error('Wishlist error:', err));
    });
  });

  // 4. Product Gallery Image Switcher
  const mainImage = document.getElementById('mainProductImage');
  const thumbs = document.querySelectorAll('.gallery-thumb');
  thumbs.forEach(function (thumb) {
    thumb.addEventListener('click', function () {
      thumbs.forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
      const targetUrl = thumb.getAttribute('data-full-img');
      if (mainImage && targetUrl) {
        mainImage.src = targetUrl;
      }
    });
  });

  // 5. Product Detail Page: Dynamic Variant Selection (Size + Colour)
  const sizeOptions = document.querySelectorAll('.size-option');
  const colourOptions = document.querySelectorAll('.colour-option');
  const hiddenSize = document.getElementById('selectedSize');
  const hiddenColour = document.getElementById('selectedColour');
  const hiddenVariantId = document.getElementById('selectedVariantId');
  const stockBadge = document.getElementById('variantStockBadge');
  const livePriceDisplay = document.getElementById('livePriceDisplay');
  const addToCartBtn = document.getElementById('addToCartBtn');
  const buyNowBtn = document.getElementById('buyNowBtn');
  const productForm = document.getElementById('productPurchaseForm');

  function updateVariantDetails() {
    if (!productForm) return;
    const productId = productForm.getAttribute('data-product-id');
    const size = hiddenSize ? hiddenSize.value : '';
    const colour = hiddenColour ? hiddenColour.value : '';

    if (!size || !colour) return;

    fetch(`/api/variant-stock?product_id=${productId}&size=${encodeURIComponent(size)}&colour=${encodeURIComponent(colour)}`)
      .then(res => res.json())
      .then(data => {
        if (hiddenVariantId) hiddenVariantId.value = data.variant_id || '';

        if (stockBadge) {
          if (!data.in_stock || data.stock_quantity <= 0) {
            stockBadge.innerHTML = '<span class="text-danger"><i class="fas fa-times-circle"></i> Out of Stock</span>';
            if (addToCartBtn) addToCartBtn.disabled = true;
            if (buyNowBtn) buyNowBtn.disabled = true;
          } else if (data.stock_quantity <= 5) {
            stockBadge.innerHTML = `<span class="text-warning"><i class="fas fa-exclamation-triangle"></i> Only ${data.stock_quantity} Left in Stock!</span>`;
            if (addToCartBtn) addToCartBtn.disabled = false;
            if (buyNowBtn) buyNowBtn.disabled = false;
          } else {
            stockBadge.innerHTML = `<span class="text-success"><i class="fas fa-check-circle"></i> In Stock (${data.stock_quantity} available)</span>`;
            if (addToCartBtn) addToCartBtn.disabled = false;
            if (buyNowBtn) buyNowBtn.disabled = false;
          }
        }

        if (livePriceDisplay && data.formatted_price) {
          livePriceDisplay.textContent = data.formatted_price;
        }

        // Adjust quantity max
        const qtyInput = document.getElementById('quantityInput');
        if (qtyInput && data.stock_quantity) {
          qtyInput.max = data.stock_quantity;
          if (parseInt(qtyInput.value) > data.stock_quantity) {
            qtyInput.value = data.stock_quantity;
          }
        }
      })
      .catch(err => console.error('Error fetching variant:', err));
  }

  sizeOptions.forEach(opt => {
    opt.addEventListener('click', function () {
      sizeOptions.forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
      if (hiddenSize) hiddenSize.value = opt.getAttribute('data-size');
      updateVariantDetails();
    });
  });

  colourOptions.forEach(opt => {
    opt.addEventListener('click', function () {
      colourOptions.forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
      if (hiddenColour) hiddenColour.value = opt.getAttribute('data-colour');
      updateVariantDetails();
    });
  });

  // Quantity +/- controls
  const btnMinus = document.querySelector('.qty-btn-minus');
  const btnPlus = document.querySelector('.qty-btn-plus');
  const qtyInput = document.getElementById('quantityInput');

  if (btnMinus && btnPlus && qtyInput) {
    btnMinus.addEventListener('click', function () {
      let val = parseInt(qtyInput.value) || 1;
      if (val > 1) qtyInput.value = val - 1;
    });

    btnPlus.addEventListener('click', function () {
      let val = parseInt(qtyInput.value) || 1;
      let max = parseInt(qtyInput.max) || 99;
      if (val < max) qtyInput.value = val + 1;
    });
  }
});

/**
 * Robust Password Visibility Toggle Helper
 * Toggles between 'password' and 'text' input types while strictly preserving
 * the current input value and preventing unwanted form submission.
 */
function togglePasswordVisibility(inputId, btn) {
  var input = document.getElementById(inputId);
  if (!input) return;
  var currentVal = input.value;
  if (input.type === 'password') {
    input.type = 'text';
    if (btn) {
      btn.innerHTML = '<i class="fas fa-eye-slash"></i>';
      btn.setAttribute('aria-label', 'Hide Password');
      btn.setAttribute('title', 'Hide Password');
    }
  } else {
    input.type = 'password';
    if (btn) {
      btn.innerHTML = '<i class="fas fa-eye"></i>';
      btn.setAttribute('aria-label', 'Show Password');
      btn.setAttribute('title', 'Show Password');
    }
  }
  if (input.value !== currentVal) {
    input.value = currentVal;
  }
}
window.togglePasswordVisibility = togglePasswordVisibility;

/**
 * Setup Live Password Strength and Real-time Validation Feedback
 * Criteria:
 * 1. At least 8 characters
 * 2. At least one uppercase letter (A-Z)
 * 3. At least one lowercase letter (a-z)
 * 4. At least one number (0-9)
 * 5. At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
 */
function setupLivePasswordValidation(passwordInputId, confirmInputId, containerId) {
  var passInput = document.getElementById(passwordInputId);
  var confirmInput = confirmInputId ? document.getElementById(confirmInputId) : null;
  var container = containerId ? document.getElementById(containerId) : null;
  if (!passInput || !container) return;

  container.innerHTML = `
    <div class="password-validation-box" style="margin-top:10px;padding:12px;background:#F8FAFC;border:1px solid var(--border-color);border-radius:var(--radius-sm);font-size:0.8rem;">
      <div style="margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <span style="font-weight:600;color:var(--text-dark);">Password Strength:</span>
          <span id="${passwordInputId}_strength_label" style="font-weight:700;color:#94A3B8;">Too Short</span>
        </div>
        <div style="width:100%;height:6px;background:#E2E8F0;border-radius:3px;overflow:hidden;">
          <div id="${passwordInputId}_strength_bar" style="width:0%;height:100%;transition:width 0.3s ease, background-color 0.3s ease;background-color:#EF4444;"></div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:8px;">
        <div id="${passwordInputId}_crit_len" style="color:#64748B;display:flex;align-items:center;gap:6px;">
          <i class="fas fa-times-circle" style="color:#CBD5E1;"></i> <span>8+ Characters</span>
        </div>
        <div id="${passwordInputId}_crit_upper" style="color:#64748B;display:flex;align-items:center;gap:6px;">
          <i class="fas fa-times-circle" style="color:#CBD5E1;"></i> <span>Uppercase (A-Z)</span>
        </div>
        <div id="${passwordInputId}_crit_lower" style="color:#64748B;display:flex;align-items:center;gap:6px;">
          <i class="fas fa-times-circle" style="color:#CBD5E1;"></i> <span>Lowercase (a-z)</span>
        </div>
        <div id="${passwordInputId}_crit_num" style="color:#64748B;display:flex;align-items:center;gap:6px;">
          <i class="fas fa-times-circle" style="color:#CBD5E1;"></i> <span>Number (0-9)</span>
        </div>
        <div id="${passwordInputId}_crit_sym" style="color:#64748B;display:flex;align-items:center;gap:6px;grid-column:span 2;">
          <i class="fas fa-times-circle" style="color:#CBD5E1;"></i> <span>Special Symbol (!@#$%...)</span>
        </div>
      </div>
      ${confirmInput ? `
      <div id="${passwordInputId}_match_box" style="margin-top:8px;padding-top:8px;border-top:1px dashed #CBD5E1;display:flex;align-items:center;gap:6px;color:#64748B;">
        <i class="fas fa-circle-notch" style="color:#CBD5E1;"></i> <span id="${passwordInputId}_match_text">Please confirm your password</span>
      </div>
      ` : ''}
    </div>
  `;

  var bar = document.getElementById(passwordInputId + '_strength_bar');
  var label = document.getElementById(passwordInputId + '_strength_label');
  var cLen = document.getElementById(passwordInputId + '_crit_len');
  var cUpper = document.getElementById(passwordInputId + '_crit_upper');
  var cLower = document.getElementById(passwordInputId + '_crit_lower');
  var cNum = document.getElementById(passwordInputId + '_crit_num');
  var cSym = document.getElementById(passwordInputId + '_crit_sym');
  var matchBox = confirmInput ? document.getElementById(passwordInputId + '_match_box') : null;
  var matchText = confirmInput ? document.getElementById(passwordInputId + '_match_text') : null;

  function updateCriteria(elem, satisfied) {
    if (!elem) return;
    var icon = elem.querySelector('i');
    if (satisfied) {
      elem.style.color = '#15803D';
      if (icon) {
        icon.className = 'fas fa-check-circle';
        icon.style.color = '#16A34A';
      }
    } else {
      elem.style.color = '#64748B';
      if (icon) {
        icon.className = 'fas fa-times-circle';
        icon.style.color = '#CBD5E1';
      }
    }
  }

  function evaluate() {
    var val = passInput.value || '';
    var hasLen = val.length >= 8;
    var hasUpper = /[A-Z]/.test(val);
    var hasLower = /[a-z]/.test(val);
    var hasNum = /[0-9]/.test(val);
    var hasSym = /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(val);

    updateCriteria(cLen, hasLen);
    updateCriteria(cUpper, hasUpper);
    updateCriteria(cLower, hasLower);
    updateCriteria(cNum, hasNum);
    updateCriteria(cSym, hasSym);

    var score = 0;
    if (hasLen) score++;
    if (hasUpper) score++;
    if (hasLower) score++;
    if (hasNum) score++;
    if (hasSym) score++;

    if (val.length === 0) {
      if (bar) {
        bar.style.width = '0%';
        bar.style.backgroundColor = '#CBD5E1';
      }
      if (label) {
        label.textContent = 'Enter password';
        label.style.color = '#94A3B8';
      }
    } else if (score <= 2) {
      if (bar) {
        bar.style.width = '35%';
        bar.style.backgroundColor = '#EF4444';
      }
      if (label) {
        label.textContent = 'Weak';
        label.style.color = '#EF4444';
      }
    } else if (score <= 4) {
      if (bar) {
        bar.style.width = '70%';
        bar.style.backgroundColor = '#F59E0B';
      }
      if (label) {
        label.textContent = 'Medium';
        label.style.color = '#F59E0B';
      }
    } else {
      if (bar) {
        bar.style.width = '100%';
        bar.style.backgroundColor = '#10B981';
      }
      if (label) {
        label.textContent = 'Strong (All criteria met)';
        label.style.color = '#10B981';
      }
    }

    if (confirmInput && matchBox && matchText) {
      var cVal = confirmInput.value || '';
      var mIcon = matchBox.querySelector('i');
      if (!cVal) {
        matchBox.style.color = '#64748B';
        if (mIcon) {
          mIcon.className = 'fas fa-circle-notch';
          mIcon.style.color = '#CBD5E1';
        }
        matchText.textContent = 'Please confirm your password';
      } else if (cVal === val) {
        matchBox.style.color = '#15803D';
        if (mIcon) {
          mIcon.className = 'fas fa-check-circle';
          mIcon.style.color = '#16A34A';
        }
        matchText.textContent = 'Passwords match';
      } else {
        matchBox.style.color = '#B91C1C';
        if (mIcon) {
          mIcon.className = 'fas fa-times-circle';
          mIcon.style.color = '#EF4444';
        }
        matchText.textContent = 'Passwords do not match';
      }
    }
  }

  passInput.addEventListener('input', evaluate);
  if (confirmInput) {
    confirmInput.addEventListener('input', evaluate);
  }
  evaluate();
}
window.setupLivePasswordValidation = setupLivePasswordValidation;

/**
 * Setup Real-Time Street Address Validation Feedback
 */
function setupAddressValidation(addressInputId, feedbackElemId) {
  var addrInput = document.getElementById(addressInputId);
  var feedback = document.getElementById(feedbackElemId);
  if (!addrInput || !feedback) return;

  function validate() {
    var raw = (addrInput.value || '').trim();
    if (!raw) {
      feedback.style.display = 'none';
      return;
    }
    feedback.style.display = 'block';

    if (raw.length < 10) {
      feedback.innerHTML = '<span style="color:#B91C1C;font-size:0.78rem;font-weight:600;"><i class="fas fa-exclamation-circle"></i> Address is too short (at least 10 characters required).</span>';
      return;
    }

    if (/(.)\1{4,}/i.test(raw)) {
      feedback.innerHTML = '<span style="color:#B91C1C;font-size:0.78rem;font-weight:600;"><i class="fas fa-times-circle"></i> Please enter a realistic address (repetitive characters detected).</span>';
      return;
    }

    var words = raw.split(/\s+/).filter(w => /[A-Za-z]/.test(w));
    if (words.length < 2) {
      feedback.innerHTML = '<span style="color:#B91C1C;font-size:0.78rem;font-weight:600;"><i class="fas fa-times-circle"></i> Please provide complete street details (at least two words).</span>';
      return;
    }

    var mashPatterns = [/asdf/i, /hjkl/i, /qwerty/i, /zxcv/i, /12345/i];
    for (var i = 0; i < mashPatterns.length; i++) {
      if (mashPatterns[i].test(raw.toLowerCase())) {
        feedback.innerHTML = '<span style="color:#B91C1C;font-size:0.78rem;font-weight:600;"><i class="fas fa-times-circle"></i> Please enter a valid Indian street address without random keystrokes.</span>';
        return;
      }
    }

    feedback.innerHTML = '<span style="color:#15803D;font-size:0.78rem;font-weight:600;"><i class="fas fa-check-circle"></i> Meaningful street address format verified.</span>';
  }

  addrInput.addEventListener('input', validate);
  if (addrInput.value) validate();
}
window.setupAddressValidation = setupAddressValidation;


