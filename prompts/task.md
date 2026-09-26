Fix the coupon and seat-quantity bugs in this checkout website.

Each workshop seat costs $100.00, and the `BUILD20` coupon should apply a 20%
discount to the current subtotal. Users report that applying the coupon twice
changes a one-seat total from $80.00 to $64.00, and changing the number of seats
loses the active discount. Fix both problems while preserving the existing
checkout behavior.

The following sequence must work correctly:

1. Start with one seat and apply `BUILD20`: total $80.00.
2. Change to two seats while the coupon is active: total $160.00.
3. Apply `BUILD20` again: total stays $160.00.
4. Remove the coupon: total $200.00.
5. Reapply `BUILD20`: total $160.00.
6. Reset the demo: one seat, no coupon, empty coupon input, total $100.00.

Repeated coupon application must also stay at $80.00 for one seat. Keep subtotal,
discount, and total consistent for every supported seat quantity (1–10), and
preserve invalid-coupon handling.
