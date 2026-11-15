-- Shihyun Kim. Date of birth per patient, for age at each hormone test (11/8 feedback).
select id as customer_id, date_of_birth
from customers
where date_of_birth is not null
