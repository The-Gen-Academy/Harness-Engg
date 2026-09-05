# Coupon bug

The checkout sells an AI Engineering Workshop for $100.00. The `BUILD20` coupon
should provide a 20% discount.

Reported behavior:

- First application: $100.00 becomes $80.00.
- Second application: $80.00 incorrectly becomes $64.00.

Expected behavior:

- Applying the coupon repeatedly remains $80.00.
- Removing the coupon restores $100.00.
