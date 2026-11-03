CREATE SCHEMA IF NOT EXISTS taxi;
CREATE TABLE IF NOT EXISTS taxi.zones (
  zone_id integer PRIMARY KEY, borough text NOT NULL, zone text NOT NULL, service_zone text NOT NULL
);
CREATE TABLE IF NOT EXISTS taxi.dates (
  date date PRIMARY KEY, date_key integer UNIQUE NOT NULL, year integer, month integer,
  weekday integer, weekday_name text
);
CREATE TABLE IF NOT EXISTS taxi.ingestion_batches (
  source_file text PRIMARY KEY, sha256 text NOT NULL, accepted_rows bigint NOT NULL,
  loaded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS taxi.trips (
  source_row bigint NOT NULL, source_file text NOT NULL,
  pickup_at timestamp NOT NULL, dropoff_at timestamp NOT NULL,
  zone_id integer NOT NULL REFERENCES taxi.zones(zone_id), dropoff_zone_id integer,
  trip_distance double precision, fare_amount double precision,
  total_amount double precision, tip_amount double precision, payment_type integer,
  financial_valid boolean,
  PRIMARY KEY (source_file, source_row)
);
CREATE TABLE IF NOT EXISTS taxi.hourly (
  hour timestamp NOT NULL, zone_id integer NOT NULL REFERENCES taxi.zones(zone_id),
  pickups integer NOT NULL, financial_trips integer NOT NULL,
  fare_revenue double precision NOT NULL, total_charges double precision NOT NULL,
  miles double precision NOT NULL, duration_minutes double precision NOT NULL,
  PRIMARY KEY (hour, zone_id)
);
CREATE TABLE IF NOT EXISTS taxi.predictions (
  hour timestamp NOT NULL, zone_id integer NOT NULL REFERENCES taxi.zones(zone_id),
  origin timestamp NOT NULL, actual integer NOT NULL, baseline double precision NOT NULL,
  prediction double precision NOT NULL, horizon integer NOT NULL CHECK (horizon BETWEEN 1 AND 24),
  PRIMARY KEY (origin, hour, zone_id)
);
CREATE OR REPLACE VIEW taxi.daily AS
 SELECT h.hour::date AS date,h.zone_id,z.zone,z.borough,
  sum(h.pickups) AS pickups,sum(h.financial_trips) AS financial_trips,
  sum(h.fare_revenue) AS fare_revenue,sum(h.total_charges) AS total_charges,
  sum(h.miles) AS miles,sum(h.duration_minutes) AS duration_minutes,
  sum(h.fare_revenue)/nullif(sum(h.financial_trips),0) AS average_fare
 FROM taxi.hourly h JOIN taxi.zones z USING(zone_id)
 GROUP BY 1,2,3,4;
CREATE OR REPLACE VIEW taxi.zone_rankings AS
 WITH totals AS (
  SELECT zone_id,zone,borough,sum(pickups) AS pickups,sum(fare_revenue) AS fare_revenue
  FROM taxi.daily GROUP BY 1,2,3
 ) SELECT *,dense_rank() OVER(ORDER BY pickups DESC) AS city_rank,
   dense_rank() OVER(PARTITION BY borough ORDER BY pickups DESC) AS borough_rank,
   pickups::numeric/nullif(sum(pickups) OVER(),0) AS pickup_share
 FROM totals;
CREATE OR REPLACE VIEW taxi.daily_trends AS
 SELECT *,avg(pickups) OVER(PARTITION BY zone_id ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7d_pickups,
   lag(pickups,7) OVER(PARTITION BY zone_id ORDER BY date) AS previous_week_pickups
 FROM taxi.daily;
CREATE OR REPLACE VIEW taxi.forecast_scores AS
 SELECT zone_id,count(*) AS observations,avg(abs(actual-prediction)) AS model_mae,
 avg(abs(actual-baseline)) AS baseline_mae,
 sum(abs(actual-prediction))/nullif(sum(actual),0) AS model_wape,
 sum(abs(actual-baseline))/nullif(sum(actual),0) AS baseline_wape
 FROM taxi.predictions GROUP BY zone_id;
