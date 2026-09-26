const PRICE_CENTS = 10_000;
const COUPON_CODE = "BUILD20";
const DISCOUNT_RATE = 0.2;

const quantityInput = document.querySelector("#quantity");
const couponInput = document.querySelector("#coupon");
const applyButton = document.querySelector("#apply-coupon");
const removeButton = document.querySelector("#remove-coupon");
const resetButton = document.querySelector("#reset-demo");
const subtotalOutput = document.querySelector("#subtotal");
const discountOutput = document.querySelector("#discount");
const totalOutput = document.querySelector("#total");
const couponMessage = document.querySelector("#coupon-message");

const state = {
  quantity: 1,
  activeCoupon: null,
  totalCents: PRICE_CENTS,
};

function formatMoney(cents) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

function showMessage(message, kind = "neutral") {
  couponMessage.textContent = message;
  couponMessage.dataset.kind = kind;
}

function render() {
  const subtotal = PRICE_CENTS * state.quantity;
  const discount = Math.max(0, subtotal - state.totalCents);

  quantityInput.value = state.quantity;
  subtotalOutput.textContent = formatMoney(subtotal);
  discountOutput.textContent = `−${formatMoney(discount)}`;
  totalOutput.textContent = formatMoney(state.totalCents);
  removeButton.hidden = state.activeCoupon === null;
}

function updateQuantity() {
  const enteredQuantity = Number(quantityInput.value);
  state.quantity = Number.isFinite(enteredQuantity)
    ? Math.min(10, Math.max(1, Math.trunc(enteredQuantity)))
    : 1;
  state.totalCents = PRICE_CENTS * state.quantity;
  render();
}

function applyCoupon() {
  if (couponInput.value.trim().toUpperCase() !== COUPON_CODE) {
    showMessage("That coupon is not valid.", "error");
    return;
  }

  state.activeCoupon = COUPON_CODE;
  state.totalCents = Math.round(state.totalCents * (1 - DISCOUNT_RATE));
  showMessage("BUILD20 applied: 20% off.", "success");
  render();
}

function removeCoupon() {
  state.activeCoupon = null;
  state.totalCents = PRICE_CENTS * state.quantity;
  couponInput.value = "";
  showMessage("Coupon removed.");
  render();
}

function resetDemo() {
  state.quantity = 1;
  state.activeCoupon = null;
  state.totalCents = PRICE_CENTS;
  couponInput.value = "";
  showMessage("");
  render();
}

quantityInput.addEventListener("change", updateQuantity);
applyButton.addEventListener("click", applyCoupon);
removeButton.addEventListener("click", removeCoupon);
resetButton.addEventListener("click", resetDemo);

render();
