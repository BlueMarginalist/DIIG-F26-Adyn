\set db `echo "$ADYN_POSTGRES_DB"`;
\set usr `echo "$ADYN_POSTGRES_USER"`;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Triggered on modification
CREATE FUNCTION Table_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
DECLARE
  TABLE_NAME VARCHAR;
  COLUMN_NAME VARCHAR; 
BEGIN
  TABLE_NAME := TG_ARGV[0];
  COLUMN_NAME := TG_ARGV[1];

  EXECUTE format('INSERT INTO %I (%I, new_values) VALUES(%L::UUID, %L::JSONB)'
                , TABLE_NAME, COLUMN_NAME, NEW.id, to_json(NEW));
  RETURN NEW;
END;
$$;

-- Prevent modification
CREATE FUNCTION Prevent_Table_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
BEGIN
  RAISE EXCEPTION 'Cannot update table %', tg_table_name;
  RETURN NULL;
END;
$$;

CREATE TABLE IF NOT EXISTS Customers (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  email VARCHAR(80) UNIQUE NOT NULL,
  new_email VARCHAR(80) UNIQUE,
  phone VARCHAR(20),
  password_hash VARCHAR(255),
  first_name VARCHAR(80),
  last_name VARCHAR(80),
  preferred_name VARCHAR(80),
  sex VARCHAR(45),
  gender VARCHAR(45),
  pronouns VARCHAR(45),
  date_of_birth DATE,
  v_code VARCHAR(255),
  v_code_used BOOLEAN DEFAULT False,
  u_code VARCHAR(255),
  u_code_used BOOLEAN DEFAULT True,
  role INTEGER,
  -- 0 = admin, 1 = editor, 2 = user/customer, 3 = purchaser, 4 = guest, 5 = por, 6 = giftee, 7 = subscriber, 8 = story sharer
  age_confirmed BOOLEAN,
  residence_confirmed BOOLEAN,
  terms_confirmed BOOLEAN,
  informed_consent_confirmed_date TIMESTAMP, -- date informed consent was signed
  ctg_opt_in BOOLEAN, -- ctg decision
  ctg_decision_date TIMESTAMP, -- date ctg decision was made
  guardian_consent_url VARCHAR(255),
  email_pref BOOLEAN NOT NULL DEFAULT True,
  referral_hero_id VARCHAR(45),
  hubspot_id VARCHAR(45),
  stripe_customer_id VARCHAR(45),
  steadymd_patient_id VARCHAR(45),
  jotform_form_id VARCHAR(45),
  npi VARCHAR(10),
  provider_id VARCHAR(22),
  subscribed_via VARCHAR(45),
  subscribed_url TEXT,
  active BOOLEAN NOT NULL DEFAULT True,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  ip VARCHAR(45),
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS HubspotTenants (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  hubspot_list_id INTEGER NOT NULL,
  customer_id uuid NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  UNIQUE(customer_id, hubspot_list_id),
  PRIMARY KEY (id, customer_id, hubspot_list_id)
);

CREATE TABLE IF NOT EXISTS MedicalBioSubmissions (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  submission_id VARCHAR(45) NOT NULL,
  jotform_form_id VARCHAR(45) NOT NULL,
  customer_id uuid NOT NULL,
  details TEXT,
  parameters TEXT,
  ip VARCHAR(45),
  completion INTEGER,
  elapsed_time INTEGER,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  UNIQUE(customer_id, jotform_form_id),
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS EmailHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  sender VARCHAR(80) NOT NULL,
  recipient VARCHAR(80) NOT NULL,
  kind VARCHAR(45) NOT NULL,
  subject VARCHAR(255),
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS ShippingAddresses (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL UNIQUE,
  first_name VARCHAR(255) NOT NULL,
  last_name VARCHAR(255) NOT NULL,
  address1 VARCHAR(255) NOT NULL,
  address2 VARCHAR(255),
  city VARCHAR(45) NOT NULL,
  state VARCHAR(2) NOT NULL,
  zip VARCHAR(45) NOT NULL,
  country VARCHAR(2) NOT NULL,
  delivery_instructions TEXT,
  is_valid BOOLEAN DEFAULT False,
  created_date TIMESTAMP NOT NULL,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS Orders (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  friendly_order_id VARCHAR(12) UNIQUE NOT NULL,
  stripe_customer_id VARCHAR(45),
  customer_id uuid NOT NULL,
  stripe_invoice_item_id VARCHAR(45),
  stripe_invoice_id VARCHAR(45),
  activation_code VARCHAR(45),
  activated BOOLEAN DEFAULT False,
  activation_date TIMESTAMP,
  por_approved BOOLEAN,
  adyn_approved BOOLEAN,
  suspended BOOLEAN,
  suspended_reason VARCHAR(255),
  name VARCHAR(255),
  sku VARCHAR(12),
  item_description VARCHAR(255),
  package_unit VARCHAR(5),
  package_unit_quantity INTEGER,
  allied_order_number VARCHAR(20),
  allied_order_date TIMESTAMP,
  status VARCHAR(45),
  date_order_placed TIMESTAMP,
  date_order_paid TIMESTAMP,
  status_checked BOOLEAN DEFAULT False,
  ip VARCHAR(45),
  created_date TIMESTAMP NOT NULL,
  modified_date TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_customer
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

-- Orders history
CREATE TABLE IF NOT EXISTS OrderHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  order_id uuid NOT NULL,
  new_values JSONB NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_order
    FOREIGN KEY (order_id)
      REFERENCES Orders(id)
      ON UPDATE CASCADE
);

CREATE TRIGGER Orders_After_Update_Trigger
  AFTER UPDATE OR INSERT ON Orders
  FOR EACH ROW
  EXECUTE PROCEDURE Table_Update_Func('orderhistory', 'order_id');

CREATE TABLE IF NOT EXISTS CouponOrders (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  friendly_order_id VARCHAR(12) UNIQUE NOT NULL,
  coupon_code VARCHAR(10) UNIQUE,
  recipient_email VARCHAR(80) NOT NULL,
  recipient_first_name VARCHAR(80),
  recipient_last_name VARCHAR(80),
  recipient_is_18_or_older BOOLEAN,
  giftor_is_legal_guardian BOOLEAN,
  stripe_invoice_item_id VARCHAR(45),
  stripe_customer_id VARCHAR(45),
  customer_id uuid NOT NULL,
  stripe_invoice_id VARCHAR(45),
  emailed_date TIMESTAMP,
  name VARCHAR(255),
  sku VARCHAR(45),
  date_order_placed TIMESTAMP,
  date_order_paid TIMESTAMP,
  ip VARCHAR(45),
  created_date TIMESTAMP NOT NULL,
  modified_date TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_customer
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

CREATE TABLE PaymentIssues (
  customer_id uuid NOT NULL,
  stripe_customer_id VARCHAR(45),
  stripe_invoice_id VARCHAR(45),
  status VARCHAR(45),
  details TEXT,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (customer_id, stripe_customer_id, stripe_invoice_id),
  FOREIGN KEY (customer_id) REFERENCES Customers(id) ON UPDATE CASCADE
);

CREATE TABLE Coupons_Redeemers (
  redeemer_id uuid NOT NULL,
  coupon_code VARCHAR(10) UNIQUE,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (redeemer_id) REFERENCES Customers(id) ON UPDATE CASCADE,
  FOREIGN KEY (coupon_code) REFERENCES CouponOrders(coupon_code) ON UPDATE CASCADE
);

CREATE TABLE Orders_Approvers (
  approver_id uuid NOT NULL,
  order_id uuid NOT NULL,
  status BOOLEAN NOT NULL,
  role INTEGER NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (approver_id) REFERENCES Customers(id) ON UPDATE CASCADE,
  FOREIGN KEY (order_id) REFERENCES Orders(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS Shipments (
  -- 1 is always saliva, 2 is always blood, Rx has its own order
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  order_id uuid NOT NULL,
  tracking_number VARCHAR(22),
  date_shipped TIMESTAMP,
  shipped_to_facility1_date TIMESTAMP,
  shipped_to_facility2_date TIMESTAMP,
  shipped_via VARCHAR(20),
  status VARCHAR(45),
  return_status1 VARCHAR(45),
  return_status2 VARCHAR(45),
  details TEXT,
  return_details1 TEXT,
  return_details2 TEXT,
  return_tracking_number1 VARCHAR(45),
  return_tracking_number2 VARCHAR(45),
  secondary_kit_id1 VARCHAR(22),
  secondary_kit_id2 VARCHAR(22),
  expiration_date1 TIMESTAMP,
  expiration_date2 TIMESTAMP,
  device_id VARCHAR(22),
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  delivered_to_customer_date TIMESTAMP,
  delivered_to_facility1_date TIMESTAMP,
  delivered_to_facility2_date TIMESTAMP,
  status_checked BOOLEAN DEFAULT False,
  PRIMARY KEY (id),
  CONSTRAINT fk_order
    FOREIGN KEY (order_id)
      REFERENCES Orders(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

CREATE TABLE Shipments_Replacements (
  old_shipment_id uuid NOT NULL,
  new_stripe_invoice_item_id VARCHAR(45) NOT NULL,
  replacer_id uuid NOT NULL,
  reason VARCHAR(255) NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (old_shipment_id, new_stripe_invoice_item_id, replacer_id),
  CONSTRAINT fk_old_shipment
    FOREIGN KEY (old_shipment_id)
      REFERENCES Shipments(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_replacer
    FOREIGN KEY (replacer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Samples (
  id VARCHAR(22) NOT NULL,
  shipment_id uuid NOT NULL,
  kind VARCHAR(7),
  -- Either KIT-SLV or KIT-BLD
  received_by_lab_date TIMESTAMP,
  processed_by_lab_date TIMESTAMP,
  file_name VARCHAR(255),
  file_url VARCHAR(255),
  file_size INT,
  downloaded_by_adyn_date TIMESTAMP,
  analyzed_by_adyn_date TIMESTAMP,
  status VARCHAR(45),
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE (id, shipment_id),
  CONSTRAINT fk_shipment
    FOREIGN KEY (shipment_id)
      REFERENCES Shipments(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

-- Samples history
CREATE TABLE IF NOT EXISTS SampleHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  sample_id VARCHAR(22) NOT NULL,
  new_values JSONB NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_sample
    FOREIGN KEY (sample_id)
      REFERENCES Samples(id)
      ON UPDATE CASCADE
);


-- Report tables -------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ResultValues (
  -- Note: This contains the text values that will be used in the report.
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  dna_sample_id VARCHAR(22) NOT NULL,
  hormone_sample_id VARCHAR(22) NOT NULL,
  medbio_1_id uuid,
  medbio_2_id uuid,
  medbio_3_id uuid,
  medbio_4_id uuid,
  version INTEGER NOT NULL,
  pipeline_output JSONB NOT NULL,  -- Results from the pipeline
  values JSONB NOT NULL,  -- Text values for the report
  background_notes JSONB,
  por_approved BOOLEAN,
  adyn_approved BOOLEAN,
  suspended BOOLEAN,
  suspended_reason VARCHAR(255),
  customer_viewed_date TIMESTAMP,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  UNIQUE (dna_sample_id, hormone_sample_id, medbio_1_id, medbio_2_id, medbio_3_id, medbio_4_id, version),
  PRIMARY KEY (id),
  CONSTRAINT fk_dna_sample
    FOREIGN KEY (dna_sample_id)
      REFERENCES Samples(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_hormone_sample
    FOREIGN KEY (hormone_sample_id)
      REFERENCES Samples(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_medbio_1
    FOREIGN KEY (medbio_1_id)
      REFERENCES MedicalBioSubmissions(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_medbio_2
    FOREIGN KEY (medbio_2_id)
      REFERENCES MedicalBioSubmissions(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_medbio_3
    FOREIGN KEY (medbio_3_id)
      REFERENCES MedicalBioSubmissions(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_medbio_4
    FOREIGN KEY (medbio_4_id)
      REFERENCES MedicalBioSubmissions(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

CREATE TABLE ResultValuesHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  result_values_id uuid NOT NULL,
  dna_sample_id VARCHAR(22) NOT NULL,
  hormone_sample_id VARCHAR(22) NOT NULL,
  medbio_1_id uuid,
  medbio_2_id uuid,
  medbio_3_id uuid,
  medbio_4_id uuid,
  version INTEGER,
  por_approved BOOLEAN,
  adyn_approved BOOLEAN,
  suspended BOOLEAN,
  suspended_reason VARCHAR(255),
  customer_viewed_date TIMESTAMP,
  FOREIGN KEY (result_values_id) REFERENCES ResultValues(id) ON UPDATE CASCADE,
  PRIMARY KEY (id)
);


-- Appointments
CREATE TABLE Appointments (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  friendly_order_id VARCHAR(12) UNIQUE NOT NULL,
  steadymd_appointment_id VARCHAR(45) NOT NULL,
  customer_id uuid NOT NULL,
  stripe_customer_id VARCHAR(45),
  provider_id VARCHAR(22),
  email_id VARCHAR(45),
  conference_link VARCHAR(255),
  emailed_date TIMESTAMP NOT NULL,
  appointment_date TIMESTAMPTZ NOT NULL,
  appointment_string VARCHAR(255),
  status VARCHAR(45) DEFAULT 'scheduled',
  confirmed_status VARCHAR(45),
  adyn_approved BOOLEAN,
  visit_notes TEXT,
  post_visit_summary TEXT,
  provider_evaluation INTEGER,
  appointment_outcome VARCHAR(22),
  follow_up_required BOOLEAN,
  bc_results_facilitate_shared_decision INTEGER,
  patient_interaction_satisfaction INTEGER,
  satisfaction_level_contribution VARCHAR(255),
  stripe_invoice_item_id VARCHAR(45),
  stripe_invoice_id VARCHAR(45),
  stripe_price_id VARCHAR(45),
  date_order_placed TIMESTAMP,
  date_order_paid TIMESTAMP,

  result_values_id uuid,

  admin_notes TEXT,
  sku VARCHAR(12),
  reason VARCHAR(255), -- Reason for appointment
  adyn_disapproved_reason VARCHAR(255),
  customer_visibility BOOLEAN DEFAULT True,

  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_result_values_id
    FOREIGN KEY (result_values_id)
      REFERENCES ResultValues(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  UNIQUE (customer_id, conference_link, emailed_date, appointment_date),
  PRIMARY KEY (id)
);

CREATE TABLE AppointmentSelections (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  kind VARCHAR(45) NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);


-- Prescriptions
CREATE TABLE RxOrders (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  friendly_order_id VARCHAR(12) UNIQUE NOT NULL,
  customer_id uuid NOT NULL,
  stripe_customer_id VARCHAR(45),
  status VARCHAR(45),

  -- Prescribing provider
  prescriber_id uuid NOT NULL,

  -- Rx details from provider
  sku VARCHAR(14),
  quantity INTEGER,
  days_supply INTEGER,
  signetur VARCHAR(255),
  note_to_pharmacy VARCHAR(4) DEFAULT 'ADYN',
  bc_prescribed BOOLEAN,
  rx_submitted_to_adyn_pharmacy BOOLEAN,

  refills_allowed INTEGER DEFAULT 0,
  customer_cost DECIMAL(10, 2),  -- Patient cost of Rx

  stripe_price_id VARCHAR(45) NOT NULL,
  stripe_invoice_item_id VARCHAR(45),
  stripe_invoice_id VARCHAR(45),
  date_order_placed TIMESTAMP,
  date_order_paid TIMESTAMP,

  customer_approved BOOLEAN,
  adyn_approved BOOLEAN,
  customer_disapproved_reason VARCHAR(255),
  adyn_disapproved_reason VARCHAR(255),
  suspended BOOLEAN,
  suspended_reason VARCHAR(255),
  customer_visibility BOOLEAN DEFAULT True,

  appointment_id uuid,

  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_prescriber_id
    FOREIGN KEY (prescriber_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_appointment_id
    FOREIGN KEY (appointment_id)
      REFERENCES Appointments(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);

-- RxOrders history
CREATE TABLE IF NOT EXISTS RxOrderHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  rxorder_id uuid NOT NULL,
  new_values JSONB NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_rxorder
    FOREIGN KEY (rxorder_id)
      REFERENCES RxOrders(id)
      ON UPDATE CASCADE
);

CREATE TRIGGER RxOrders_After_Update_Trigger
  AFTER UPDATE OR INSERT ON RxOrders
  FOR EACH ROW
  EXECUTE PROCEDURE Table_Update_Func('rxorderhistory', 'rxorder_id');


CREATE TABLE IF NOT EXISTS RxShipments (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  order_number VARCHAR(10),
  rx_order_id uuid NOT NULL,
  email_id VARCHAR(45),
  tracking_number VARCHAR(45),
  date_shipped TIMESTAMP,
  shipped_via VARCHAR(20),
  first_name VARCHAR(80),
  last_name VARCHAR(80),
  address1 VARCHAR(255) NOT NULL,
  address2 VARCHAR(255),
  city VARCHAR(45) NOT NULL,
  state VARCHAR(2) NOT NULL,
  zip VARCHAR(45) NOT NULL,
  status VARCHAR(45),
  status_checked BOOLEAN DEFAULT False,
  details TEXT,
  delivered_to_customer_date TIMESTAMP,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_customer
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_rx_order
    FOREIGN KEY (rx_order_id)
      REFERENCES RxOrders(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

CREATE TABLE RxOrders_Approvers (
  approver_id uuid NOT NULL,
  rx_order_id uuid NOT NULL,
  status BOOLEAN NOT NULL,
  role INTEGER NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (approver_id) REFERENCES Customers(id) ON UPDATE CASCADE,
  FOREIGN KEY (rx_order_id) REFERENCES RxOrders(id) ON UPDATE CASCADE
);


-- RxShipments history
CREATE TABLE IF NOT EXISTS RxShipmentHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  rxshipment_id uuid NOT NULL,
  new_values JSONB NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_rxshipment
    FOREIGN KEY (rxshipment_id)
      REFERENCES RxShipments(id)
      ON UPDATE CASCADE
);

CREATE TRIGGER RxShipments_After_Update_Trigger
  AFTER UPDATE OR INSERT ON RxShipments
  FOR EACH ROW
  EXECUTE PROCEDURE Table_Update_Func('rxshipmenthistory', 'rxshipment_id');

CREATE TABLE IF NOT EXISTS RxWritten (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  rx_number VARCHAR(15) NOT NULL,
  rx_written_date_time TIMESTAMP NOT NULL,
  rx_creation_date_time TIMESTAMP NOT NULL,
  rx_expiration_date_time TIMESTAMP NOT NULL,
  script_status VARCHAR(1) NOT NULL,
  ndc VARCHAR(15) NOT NULL,
  patient_id VARCHAR(15) NOT NULL,
  zip_code VARCHAR(10) NOT NULL,
  total_fills FLOAT,
  total_qty_authorized FLOAT NOT NULL,
  rx_source VARCHAR(3) NOT NULL,
  auto_refill VARCHAR(1),
  npi_provider_number VARCHAR(15) NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  customer_first_name VARCHAR(80),
  customer_last_name VARCHAR(80),
  customer_dob DATE,
  customer_email VARCHAR(80),
  PRIMARY KEY (id),
  UNIQUE (rx_number, rx_written_date_time, rx_creation_date_time, rx_expiration_date_time, script_status, ndc, patient_id, zip_code, total_qty_authorized, rx_source, npi_provider_number)
);

CREATE TABLE IF NOT EXISTS RxPacked (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  shipment_order VARCHAR(20) NOT NULL,
  order_receipt_date_time TIMESTAMP NOT NULL,
  rx_number VARCHAR(15) NOT NULL,
  fill_number VARCHAR(15) NOT NULL,
  qty_req FLOAT NOT NULL,
  qty_left FLOAT,
  ship_to_address1 VARCHAR(255),
  ship_to_address2 VARCHAR(255),
  ship_to_city VARCHAR(45),
  ship_to_state VARCHAR(2),
  ship_to_zip_code VARCHAR(15),
  packed_date_time TIMESTAMP,
  ship_date_time TIMESTAMP,
  bin_number VARCHAR(15),
  patient_amount_if_cash_or_house_charge FLOAT,
  patient_copay_if_insured FLOAT,
  primary_ins_name VARCHAR(50),
  primary_ins_bin VARCHAR(25),
  primary_ins_pcn VARCHAR(25),
  primary_ins_rx_group VARCHAR(25),
  primary_ins_plan_paid_amount FLOAT,
  primary_ins_copay FLOAT,
  primary_ins_disp_fee FLOAT,
  sec_ins_name VARCHAR(50),
  sec_ins_bin VARCHAR(25),
  sec_ins_pcn VARCHAR(25),
  sec_ins_rx_group VARCHAR(25),
  sec_ins_plan_paid_amount FLOAT,
  sec_ins_copay FLOAT,
  sec_ins_disp_fee FLOAT,
  drug_acquisition_cost FLOAT,
  shipping_carrier_name VARCHAR(50),
  fill_date TIMESTAMP,
  tracking_number VARCHAR(50),
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE (shipment_order, order_receipt_date_time)
);


CREATE TABLE IF NOT EXISTS RxMatches (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  rx_order_id uuid,
  rx_packed_id uuid,
  rx_shipments_id uuid,
  status VARCHAR(45),
  matcher_id uuid NOT NULL,
  resolution VARCHAR(45),
  reason_for_no_charge VARCHAR(45),
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_rx_order_id
    FOREIGN KEY (rx_order_id)
      REFERENCES RxOrders(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_rx_packed_id
    FOREIGN KEY (rx_packed_id)
      REFERENCES RxPacked(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_rx_shipments_id
    FOREIGN KEY (rx_shipments_id)
      REFERENCES RxShipments(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_matcher_id
    FOREIGN KEY (matcher_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id),
  UNIQUE (rx_order_id, rx_packed_id, rx_shipments_id)
);


-- RxMatches history
CREATE TABLE IF NOT EXISTS RxMatchHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  rxmatch_id uuid NOT NULL,
  new_values JSONB NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_rxmatch
    FOREIGN KEY (rxmatch_id)
      REFERENCES RxMatches(id)
      ON UPDATE CASCADE
);

CREATE TRIGGER RxMatches_After_Update_Trigger
  AFTER UPDATE OR INSERT ON RxMatches
  FOR EACH ROW
  EXECUTE PROCEDURE Table_Update_Func('rxmatchhistory', 'rxmatch_id');

CREATE OR REPLACE FUNCTION Sample_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    INSERT INTO SampleHistory(sample_id, new_values)
    VALUES(OLD.id, to_json(NEW));
  ELSEIF TG_OP = 'INSERT' THEN
    INSERT INTO SampleHistory(sample_id, new_values)
    VALUES(NEW.id, to_json(NEW));
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER Sample_Update_Trigger
  AFTER UPDATE OR INSERT
  ON "samples"
  FOR EACH ROW
  EXECUTE PROCEDURE Sample_Update_Func();

-- Bioinformatics Tables ------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Variants (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  adyn_id VARCHAR(80) NOT NULL,
  gsa_id VARCHAR(32) DEFAULT NULL,
  chrom INTEGER NOT NULL,
  position INTEGER NOT NULL,

  -- 0: A, 1: C, 2: G, 3: T; 4 and up are for indels
  ref_value INTEGER NOT NULL,
  allele_map JSONB NULL,

  PRIMARY KEY (id),
  UNIQUE (adyn_id),
  UNIQUE (gsa_id)
);

CREATE TABLE IF NOT EXISTS GenotypeValues (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  variant_id uuid NOT NULL,
  sample_id VARCHAR(22) NOT NULL,
  genotype_value_1 INTEGER NOT NULL,
  genotype_value_2 INTEGER NOT NULL,
  gencall_score FLOAT NOT NULL,
  imputed BOOLEAN NOT NULL,
  format_string JSONB NOT NULL,
  info_string JSONB NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  UNIQUE (customer_id, variant_id, sample_id),
  PRIMARY KEY (id),
  CONSTRAINT fk_customer
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_variant
    FOREIGN KEY (variant_id)
      REFERENCES Variants(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_sample
    FOREIGN KEY (sample_id)
      REFERENCES Samples(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Hormones (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  name VARCHAR(50) NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  UNIQUE (name),
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS HormoneValues (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  hormone_id uuid NOT NULL,
  sample_id VARCHAR(22) NOT NULL,
  hormone_value FLOAT,
  ref_high FLOAT,
  ref_low FLOAT,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  UNIQUE (customer_id, hormone_id, sample_id),
  PRIMARY KEY (id),
  CONSTRAINT fk_customer
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_hormone
    FOREIGN KEY (hormone_id)
      REFERENCES Hormones(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_sample
    FOREIGN KEY (sample_id)
      REFERENCES Samples(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE
);


CREATE OR REPLACE FUNCTION ResultValues_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    INSERT INTO ResultValuesHistory(result_values_id, dna_sample_id, hormone_sample_id, medbio_1_id, medbio_2_id, medbio_3_id, medbio_4_id, version, por_approved, adyn_approved, suspended, suspended_reason, customer_viewed_date)
    VALUES(NEW.id, NEW.dna_sample_id, NEW.hormone_sample_id, NEW.medbio_1_id, NEW.medbio_2_id, NEW.medbio_3_id, NEW.medbio_4_id, NEW.version, NEW.por_approved, NEW.adyn_approved, NEW.suspended, NEW.suspended_reason, NEW.customer_viewed_date);
  END IF;
  RETURN NEW;
RETURN NEW;
END;
$$;

CREATE TRIGGER ResultValues_Update_Trigger
  AFTER UPDATE OR INSERT
  ON "resultvalues"
  FOR EACH ROW
  EXECUTE PROCEDURE ResultValues_Update_Func();

CREATE TABLE ResultValues_Approvers (
  approver_id uuid NOT NULL,
  result_values_id uuid NOT NULL,
  status BOOLEAN NOT NULL,
  role INTEGER NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (approver_id) REFERENCES Customers(id) ON UPDATE CASCADE,
  FOREIGN KEY (result_values_id) REFERENCES ResultValues(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS RxOrders_ResultValues (
  rx_order_id uuid NOT NULL,
  result_values_id uuid NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_rx_order_id
    FOREIGN KEY (rx_order_id)
      REFERENCES RxOrders(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_result_values_id
    FOREIGN KEY (result_values_id)
      REFERENCES ResultValues(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (rx_order_id, result_values_id)
);

CREATE TABLE ShippingAddresses_Editors (
  editor_id uuid NOT NULL,
  shipping_address_id uuid NOT NULL,
  new_values JSONB NOT NULL,
  role INTEGER NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (editor_id) REFERENCES Customers(id) ON UPDATE CASCADE,
  FOREIGN KEY (shipping_address_id) REFERENCES ShippingAddresses(id) ON UPDATE CASCADE
);

-- Profile Completions
CREATE TABLE IF NOT EXISTS ProfileCompletions (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  complete BOOLEAN NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);

CREATE OR REPLACE FUNCTION Customer_ProfileCompletion_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
DECLARE
  last_record BOOLEAN;
  record_id uuid;
BEGIN
  IF TG_ARGV[0] = 'Customers' THEN
    record_id = OLD.id;
  ELSIF TG_ARGV[0] = 'ShippingAddresses' THEN
    record_id = OLD.customer_id;
  END IF;
  IF
    (SELECT COUNT(*) > 0
    FROM Customers c
    LEFT JOIN ShippingAddresses s
    ON c.id = s.customer_id
    WHERE s.is_valid = True
    AND c.first_name IS NOT NULL
    AND c.first_name <> ''
    AND c.last_name IS NOT NULL
    AND c.last_name <> ''
    AND c.phone IS NOT NULL
    AND c.phone <> ''
    AND c.phone <> '(555) 555 - 5555'
    AND c.date_of_birth IS NOT NULL
    AND c.sex = 'female'
    AND c.id = record_id) THEN
      SELECT p.complete
        FROM ProfileCompletions p
        WHERE record_id = p.customer_id
        ORDER BY p.created_date DESC
        LIMIT 1
        INTO last_record;
      IF last_record IS NULL OR last_record = False THEN
        INSERT INTO ProfileCompletions(customer_id, complete)
        VALUES(record_id, True);
      END IF;
  ELSIF
    (SELECT COUNT(*) > 0
    FROM Customers c
    LEFT JOIN ShippingAddresses s
    ON c.id = s.customer_id
    WHERE c.id = record_id
    AND (s.is_valid = False
      OR c.first_name IS NULL
      OR c.first_name = ''
      OR c.last_name IS NULL
      OR c.last_name = ''
      OR c.phone IS NULL
      OR c.phone = ''
      OR c.phone = '(555) 555 - 5555'
      OR c.date_of_birth IS NULL
      OR c.sex <> 'female')) THEN
        IF (SELECT p.complete FROM ProfileCompletions p
          WHERE record_id = p.customer_id
          ORDER BY p.created_date DESC
          LIMIT 1) = True THEN
            INSERT INTO ProfileCompletions(customer_id, complete)
            VALUES(record_id, False);
        END IF;
  END IF;
RETURN NEW;
END;
$$;

CREATE TRIGGER CustomerUpdate_Complete_Trigger
  AFTER UPDATE
  ON "customers"
  FOR EACH ROW
  EXECUTE PROCEDURE Customer_ProfileCompletion_Func('Customers');

CREATE TRIGGER AddressUpdate_Complete_Trigger
  AFTER UPDATE
  ON "shippingaddresses"
  FOR EACH ROW
  EXECUTE PROCEDURE Customer_ProfileCompletion_Func('ShippingAddresses');

-- Order Status History
CREATE TABLE OrderStatuses (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  order_id uuid NOT NULL,
  old_status VARCHAR(45),
  new_status VARCHAR(45) NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES Orders(id) ON UPDATE CASCADE,
  PRIMARY KEY (id)
);

CREATE OR REPLACE FUNCTION Order_Status_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.status <> OLD.status THEN
      INSERT INTO OrderStatuses(order_id, old_status, new_status)
      VALUES(NEW.id, OLD.status, NEW.status);
    END IF;
  ELSE
    INSERT INTO OrderStatuses(order_id, old_status, new_status)
    VALUES(NEW.id, '', NEW.status);
  END IF;
  RETURN NEW;
RETURN NEW;
END;
$$;

CREATE TRIGGER Order_Update_Trigger
  AFTER UPDATE OR INSERT
  ON "orders"
  FOR EACH ROW
  EXECUTE PROCEDURE Order_Status_Update_Func();

-- Shipment History
CREATE TABLE ShipmentStatuses (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  shipment_id uuid NOT NULL,
  status VARCHAR(45),
  return_status1 VARCHAR(45),
  return_status2 VARCHAR(45),
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (shipment_id) REFERENCES Shipments(id) ON UPDATE CASCADE,
  PRIMARY KEY (id)
);

CREATE OR REPLACE FUNCTION Shipment_Status_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
DECLARE
  status VARCHAR(45);
  return_status1 VARCHAR(45);
  return_status2 VARCHAR(45);
  changed_flag BOOLEAN;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    status = OLD.status;
    return_status1 = OLD.return_status1;
    return_status2 = OLD.return_status2;
    changed_flag = False;
    IF (NEW.status <> OLD.status) OR (NEW.status IS NOT NULL AND OLD.status IS NULL) OR (NEW.status IS NULL AND OLD.status IS NOT NULL) THEN
      status = NEW.status;
      changed_flag = True;
    END IF;
    IF (NEW.return_status1 <> OLD.return_status1) OR (NEW.return_status1 IS NOT NULL AND OLD.return_status1 IS NULL) OR (NEW.return_status1 IS NULL AND OLD.return_status1 IS NOT NULL) THEN
      return_status1 = NEW.return_status1;
      changed_flag = True;
    END IF;
    IF (NEW.return_status2 <> OLD.return_status2) OR (NEW.return_status2 IS NOT NULL AND OLD.return_status2 IS NULL) OR (NEW.return_status2 IS NULL AND OLD.return_status2 IS NOT NULL) THEN
      return_status2 = NEW.return_status2;
      changed_flag = True;
    END IF;
    IF (changed_flag = True) THEN
      INSERT INTO ShipmentStatuses(shipment_id, status, return_status1, return_status2)
      VALUES(NEW.id, status, return_status1, return_status2);
    END IF;
  ELSE
    IF (NEW.status IS NOT NULL) OR (NEW.return_status1 IS NOT NULL) OR (NEW.return_status2 IS NOT NULL) THEN
      INSERT INTO ShipmentStatuses(shipment_id, status, return_status1, return_status2)
      VALUES(NEW.id, NEW.status, NEW.return_status1, NEW.return_status2);
    END IF;
  END IF;
  RETURN NEW;
RETURN NEW;
END;
$$;

-- DROP TRIGGER IF EXISTS Shipment_Update_Trigger
  -- ON "shipments";
CREATE TRIGGER Shipment_Update_Trigger
  BEFORE UPDATE
  ON "shipments"
  FOR EACH ROW
  EXECUTE PROCEDURE Shipment_Status_Update_Func();

-- DROP TRIGGER IF EXISTS Shipment_Insert_Trigger
  -- ON "shipments";
CREATE TRIGGER Shipment_Insert_Trigger
  AFTER INSERT
  ON "shipments"
  FOR EACH ROW
  EXECUTE PROCEDURE Shipment_Status_Update_Func();


-- Customer History
CREATE TABLE CustomerHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  new_values JSONB NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES Customers(id) ON UPDATE CASCADE,
  PRIMARY KEY (id)
);

CREATE OR REPLACE FUNCTION Customer_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    INSERT INTO CustomerHistory(customer_id, new_values)
    VALUES(NEW.id, to_json(NEW));
  ELSE
    INSERT INTO CustomerHistory(customer_id, new_values)
    VALUES(NEW.id, to_json(NEW));
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER Customer_Update_Trigger
  AFTER UPDATE OR INSERT
  ON "customers"
  FOR EACH ROW
  EXECUTE PROCEDURE Customer_Update_Func();

CREATE TABLE Subscriptions (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  stripe_invoice_item_id VARCHAR(45),
  stripe_invoice_id VARCHAR(45),
  stripe_price_id VARCHAR(45),
  date_order_paid TIMESTAMP,
  customer_id uuid NOT NULL,
  active BOOLEAN DEFAULT True,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);

CREATE TABLE SubscriptionHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  subscription_id uuid NOT NULL,
  active BOOLEAN NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_subscription_id
    FOREIGN KEY (subscription_id)
      REFERENCES Subscriptions(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);

-- For Mocking SteadyMD in Staging Only
CREATE TABLE FakeSteadyMdAppointments (
  id SERIAL,
  provider VARCHAR(455) NOT NULL,
  patient VARCHAR(455) NOT NULL,
  patient_id VARCHAR(45) NOT NULL,
  provider_id VARCHAR(22) NOT NULL,
  appointment_date TIMESTAMPTZ NOT NULL,
  zoom_url VARCHAR(255),
  status VARCHAR(45),
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  PRIMARY KEY (id)
);

-- Appointment History
CREATE TABLE AppointmentHistory (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  appointment_id uuid NOT NULL,
  new_values JSONB NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (appointment_id) REFERENCES Appointments(id) ON UPDATE CASCADE,
  PRIMARY KEY (id)
);

CREATE OR REPLACE FUNCTION Appointment_Update_Func()
  RETURNS TRIGGER
  LANGUAGE PLPGSQL VOLATILE
  AS
$$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    INSERT INTO AppointmentHistory(appointment_id, new_values)
    VALUES(NEW.id, to_json(NEW));
  ELSE
    INSERT INTO AppointmentHistory(appointment_id, new_values)
    VALUES(NEW.id, to_json(NEW));
  END IF;
  RETURN NEW;
RETURN NEW;
END;
$$;

CREATE TRIGGER Appointment_Update_Trigger
  AFTER UPDATE OR INSERT
  ON "appointments"
  FOR EACH ROW
  EXECUTE PROCEDURE Appointment_Update_Func();

CREATE TABLE IF NOT EXISTS Appointments_ResultValues (
  appointment_id uuid NOT NULL,
  result_values_id uuid NOT NULL,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date TIMESTAMP,
  CONSTRAINT fk_appointment_id
    FOREIGN KEY (appointment_id)
      REFERENCES Appointments(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_result_values_id
    FOREIGN KEY (result_values_id)
      REFERENCES ResultValues(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (appointment_id, result_values_id)
);

-- ADYNFORM (deprecated)
CREATE TABLE IF NOT EXISTS AdynForm(
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  form_type VARCHAR(45),
  form_fields JSONB NOT NULL,
  modified_date TIMESTAMP,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  version DOUBLE PRECISION,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS MedicalHistory(
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  medical_history_form JSONB,
  ip VARCHAR(45),
  notes TEXT,
  modified_date TIMESTAMP,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_date TIMESTAMP,
  adyn_form_id uuid NOT NULL,
  form_display_name VARCHAR(45),
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_adyn_form_id
    FOREIGN KEY (adyn_form_id)
      REFERENCES AdynForm(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  UNIQUE(customer_id),
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS CustomerIntake(
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  intake_form JSONB,
  intake_type VARCHAR(45),
  modified_date TIMESTAMP,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_date TIMESTAMP,
  notes TEXT,
  ip VARCHAR(45),
  adyn_form_id uuid NOT NULL,
  form_display_name VARCHAR(45),
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_adyn_form_id
    FOREIGN KEY (adyn_form_id)
      REFERENCES AdynForm(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS CustomerCheckIn(
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  customer_id uuid NOT NULL,
  order_id uuid NOT NULL,
  check_in_form JSONB,
  product_type VARCHAR(45),
  check_in_type VARCHAR(45),
  modified_date TIMESTAMP,
  created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_date TIMESTAMP,
  ip VARCHAR(45),
  notes TEXT, 
  adyn_form_id uuid NOT NULL,
  CONSTRAINT fk_customer_id
    FOREIGN KEY (customer_id)
      REFERENCES Customers(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_order_id
    FOREIGN KEY (order_id)
      REFERENCES Orders(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  CONSTRAINT fk_adyn_form_id
    FOREIGN KEY (adyn_form_id)
      REFERENCES AdynForm(id)
      ON UPDATE CASCADE
      ON DELETE CASCADE,
  PRIMARY KEY (id)
);

-- ADYNFORM V1 AUDIT TABLES
-- CREATE TABLE AdynFormHistory (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- adynform_id uuid NOT NULL,
  -- new_values JSONB NOT NULL,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (adynform_id) REFERENCES AdynForm(id) ON UPDATE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TRIGGER AdynForm_After_Update_Trigger
  -- AFTER UPDATE OR INSERT ON AdynForm
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Table_Update_Func('adynformhistory', 'adynform_id');

-- CREATE TRIGGER AdynForm_History_Before_Update_Delete_Trigger
  -- BEFORE UPDATE OR DELETE ON adynform_history
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Prevent_Table_Update_Func();

-- CREATE TABLE MedicalHIstoryHistory (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- medical_history_id uuid NOT NULL,
  -- new_values JSONB NOT NULL,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (medical_history_id) REFERENCES MedicalHIstory(id) ON UPDATE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TRIGGER MedicalHistory_After_Update_Trigger
  -- AFTER UPDATE OR INSERT ON MedicalHistory
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Table_Update_Func('medicalhistoryhistory', 'medical_history_id');

-- CREATE TABLE CustomerIntakeHistory (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- customer_intake_id uuid NOT NULL,
  -- new_values JSONB NOT NULL,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (customer_intake_id) REFERENCES CustomerIntake(id) ON UPDATE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TRIGGER CustomerCheckin_After_Update_Trigger
  -- AFTER UPDATE OR INSERT ON CustomerIntake
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Table_Update_Func('customerintakehistory', 'customer_intake_id');

-- CREATE TABLE CustomerCheckinHistory (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- customer_checkin_id uuid NOT NULL,
  -- new_values JSONB NOT NULL,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (customer_checkin_id) REFERENCES CustomerCheckin(id) ON UPDATE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TRIGGER CustomerCheckin_After_Update_Trigger
  -- AFTER UPDATE OR INSERT ON CustomerCheckin
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Table_Update_Func('customercheckinhistory', 'customer_checkin_id');

-- CREATE TABLE IF NOT EXISTS Cohorts (
  -- id VARCHAR(45) NOT NULL,
  -- created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- modified TIMESTAMP,
  -- PRIMARY KEY (id)
-- );

-- ADYNFORM V2
-- CREATE TABLE IF NOT EXISTS Questions(
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- label VARCHAR(45),
  -- form_type VARCHAR(45),
  -- form_fields JSONB NOT NULL,
  -- validation TEXT,
  -- conditions TEXT,
  -- modified_date TIMESTAMP,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- PRIMARY KEY (id)
-- );

-- CREATE TABLE QuestionHistory (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- question_id uuid NOT NULL,
  -- new_values JSONB NOT NULL,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (question_id) REFERENCES Questions(id) ON UPDATE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TRIGGER Question_History_Before_Update_Delete_Trigger
  -- BEFORE UPDATE OR DELETE ON question_history
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Prevent_Table_Update_Func();

-- CREATE TRIGGER Question_After_Update_Trigger
  -- AFTER UPDATE OR INSERT ON Questions
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Table_Update_Func('questionhistory', 'question_id');

-- CREATE TABLE IF NOT EXISTS Modules(
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- name VARCHAR(80)
  -- -- trigger_label VARCHAR(45),
  -- -- trigger_logic TEXT (not feasible to store in DB at the moment)
  -- modified_date TIMESTAMP,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- version DOUBLE PRECISION,
  -- PRIMARY KEY (id)
-- );

-- CREATE TABLE ModuleHistory (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- module_id uuid NOT NULL,
  -- new_values JSONB NOT NULL,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (module_id) REFERENCES Modules(id) ON UPDATE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TRIGGER Module_History_Before_Update_Delete_Trigger
  -- BEFORE UPDATE OR DELETE ON module_history
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Prevent_Table_Update_Func();

-- CREATE TRIGGER Module_After_Update_Trigger
  -- AFTER UPDATE OR INSERT ON Modules
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Table_Update_Func('modulehistory', 'module_id');

-- CREATE TABLE Modules_Questions (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- modules_id uuid NOT NULL,
  -- question_id uuid NOT NULL,
  -- version DOUBLE PRECISION,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (modules_id) REFERENCES Modules(id) ON UPDATE CASCADE,
  -- FOREIGN KEY (question_id) REFERENCES Questions(id) ON UPDATE CASCADE
-- );

-- CREATE TABLE IF NOT EXISTS Answers(
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- customer_id uuid NOT NULL,
  -- question_id uuid NOT NULL,
  -- order_id uuid,
  -- form_type VARCHAR(45),
  -- form_fields JSONB NOT NULL,
  -- modified_date TIMESTAMP,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- completed_date TIMESTAMP,
  -- ip VARCHAR(45),
  -- notes TEXT, 
  -- CONSTRAINT fk_customer_id
    -- FOREIGN KEY (customer_id)
      -- REFERENCES Customers(id)
      -- ON UPDATE CASCADE
      -- ON DELETE CASCADE,
  -- CONSTRAINT fk_order_id
    -- FOREIGN KEY (order_id)
      -- REFERENCES Orders(id)
      -- ON UPDATE CASCADE
      -- ON DELETE CASCADE,
  -- CONSTRAINT fk_question_id
    -- FOREIGN KEY (question_id)
      -- REFERENCES Questions(id)
      -- ON UPDATE CASCADE
      -- ON DELETE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TABLE AnswerHistory (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- answer_id uuid NOT NULL,
  -- new_values JSONB NOT NULL,
  -- created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- FOREIGN KEY (answer_id) REFERENCES Answers(id) ON UPDATE CASCADE,
  -- PRIMARY KEY (id)
-- );

-- CREATE TRIGGER Answer_History_Before_Update_Delete_Trigger
  -- BEFORE UPDATE OR DELETE ON answer_history
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Prevent_Table_Update_Func();

-- CREATE TRIGGER Answer_After_Update_Trigger
  -- AFTER UPDATE OR INSERT ON Answers
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE Table_Update_Func('answerhistory', 'answer_id');

-- Provider Customers
-- CREATE TABLE IF NOT EXISTS Providers_Customers (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- provider_id uuid NOT NULL,
  -- customer_id uuid NOT NULL,
  -- created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- UNIQUE (customer_id, provider_id),
  -- PRIMARY KEY (customer_id, provider_id),
  -- CONSTRAINT fk_provider
    -- FOREIGN KEY (provider_id)
      -- REFERENCES Customers(id)
      -- ON UPDATE CASCADE,
  -- CONSTRAINT fk_customer
    -- FOREIGN KEY (customer_id)
      -- REFERENCES Customers(id)
      -- ON UPDATE CASCADE
-- );

-- CREATE TABLE IF NOT EXISTS Providers_Customers_History (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- provider_id uuid NOT NULL,
  -- customer_id uuid NOT NULL,
  -- entered BOOLEAN NOT NULL,
  -- created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- PRIMARY KEY (id),
  -- CONSTRAINT fk_provider
    -- FOREIGN KEY (provider_id)
      -- REFERENCES Customers(id)
      -- ON UPDATE CASCADE,
  -- CONSTRAINT fk_customer
    -- FOREIGN KEY (customer_id)
      -- REFERENCES Customers(id)
      -- ON UPDATE CASCADE
-- );
-- CREATE OR REPLACE FUNCTION provider_customer_insert_func()
  -- RETURNS TRIGGER
  -- LANGUAGE PLPGSQL VOLATILE
  -- AS
-- $$
-- BEGIN
  -- INSERT INTO provider_customer_history(provider_id, customer_id, entered)
  -- VALUES(NEW.provider_id, NEW.customer_id, True);
  -- RETURN NEW;
-- END;
-- $$;

-- CREATE OR REPLACE FUNCTION provider_customer_delete_func()
  -- RETURNS TRIGGER
  -- LANGUAGE PLPGSQL VOLATILE
  -- AS
-- $$
-- BEGIN
  -- INSERT INTO provider_customer_history(provider_id, customer_id, entered)
  -- VALUES(OLD.provider_id, OLD.customer_id, False);
  -- RETURN OLD;
-- END;
-- $$;

-- CREATE TRIGGER provider_customer_insert_trigger
  -- AFTER INSERT
  -- ON provider_customer
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE provider_customer_insert_func();

-- CREATE TRIGGER provider_customer_delete_trigger
  -- AFTER DELETE
  -- ON provider_customer
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE provider_customer_delete_func();

-- CREATE TRIGGER provider_customer_before_update_trigger
  -- BEFORE UPDATE ON provider_customer
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE update_modified();

-- CREATE TRIGGER provider_customer_history_before_update_delete_trigger
  -- BEFORE UPDATE OR DELETE ON provider_customer_history
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE prevent_table_update_func();

-- -- Networks
-- CREATE TABLE IF NOT EXISTS Customers_Networks (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- customer_id uuid NOT NULL,
  -- network_id VARCHAR(45) NOT NULL,
  -- created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- UNIQUE (customer_id, network_id),
  -- PRIMARY KEY (customer_id, network_id),
  -- CONSTRAINT fk_customer
    -- FOREIGN KEY (customer_id)
      -- REFERENCES Customers(id)
      -- ON UPDATE CASCADE,
  -- CONSTRAINT fk_network
    -- FOREIGN KEY (network_id)
      -- REFERENCES Networks(id)
      -- ON UPDATE CASCADE
-- );

-- CREATE TABLE IF NOT EXISTS Customers_Networks_History (
  -- id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- customer_id uuid NOT NULL,
  -- network_id VARCHAR(45) NOT NULL,
  -- entered BOOLEAN NOT NULL,
  -- created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- PRIMARY KEY (id),
  -- CONSTRAINT fk_customer
    -- FOREIGN KEY (customer_id)
      -- REFERENCES customer(id)
      -- ON UPDATE CASCADE,
  -- CONSTRAINT fk_network
    -- FOREIGN KEY (network_id)
      -- REFERENCES network(id)
      -- ON UPDATE CASCADE
-- );
-- CREATE OR REPLACE FUNCTION customer_network_insert_func()
  -- RETURNS TRIGGER
  -- LANGUAGE PLPGSQL VOLATILE
  -- AS
-- $$
-- BEGIN
  -- INSERT INTO customer_network_history(customer_id, network_id, entered)
  -- VALUES(NEW.customer_id, NEW.network_id, True);
  -- RETURN NEW;
-- END;
-- $$;

-- CREATE OR REPLACE FUNCTION customer_network_delete_func()
  -- RETURNS TRIGGER
  -- LANGUAGE PLPGSQL VOLATILE
  -- AS
-- $$
-- BEGIN
  -- INSERT INTO customer_network_history(customer_id, network_id, entered)
  -- VALUES(OLD.customer_id, OLD.network_id, False);
  -- RETURN OLD;
-- END;
-- $$;

-- CREATE TRIGGER customer_network_insert_trigger
  -- AFTER INSERT
  -- ON customer_network
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE customer_network_insert_func();

-- CREATE TRIGGER customer_network_delete_trigger
  -- AFTER DELETE
  -- ON customer_network
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE customer_network_delete_func();

-- CREATE TRIGGER customer_network_before_update_trigger
  -- BEFORE UPDATE ON customer_network
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE update_modified();

-- CREATE TRIGGER customer_network_history_before_update_delete_trigger
  -- BEFORE UPDATE OR DELETE ON customer_network_history
  -- FOR EACH ROW
  -- EXECUTE PROCEDURE prevent_table_update_func();
