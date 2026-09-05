Fix the coupon bug in this checkout website.

The `BUILD20` coupon should apply a 20% discount. Users report that the first
application changes the total from $100.00 to $80.00, but applying it a second
time incorrectly changes the total to $64.00. The total should remain $80.00.

