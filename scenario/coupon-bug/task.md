# Coupon and seat-quantity bugs

The checkout sells AI Engineering Workshop seats for $100.00 each. The `BUILD20`
coupon should provide a 20% discount on the current subtotal for 1–10 seats.

Reported behavior:

- First application at one seat: $100.00 becomes $80.00.
- Second application at one seat: $80.00 incorrectly becomes $64.00.
- Changing to two seats while the coupon is active incorrectly restores the
  undiscounted $200.00 total.

Expected sequence:

1. Apply `BUILD20` at one seat: total $80.00.
2. Change to two seats while the coupon is active: total $160.00.
3. Apply `BUILD20` again: total stays $160.00.
4. Remove the coupon: total $200.00.
5. Reapply `BUILD20`: total $160.00.
6. Reset the demo: one seat, no coupon, empty coupon input, total $100.00.

Repeated coupon application must also stay at $80.00 for one seat. Keep subtotal,
discount, and total consistent for every supported seat quantity (1–10), and
preserve invalid-coupon handling.
