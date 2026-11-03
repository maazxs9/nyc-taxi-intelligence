-- Which zones account for most observed pickups?
SELECT zone,borough,pickups,city_rank,round(100*pickup_share,2) AS pct_of_pickups
FROM taxi.zone_rankings ORDER BY city_rank LIMIT 15;

-- Hourly patterns: average per observed wall-clock hour, including zero bins.
SELECT z.zone,extract(isodow FROM h.hour) AS weekday,extract(hour FROM h.hour) AS hour,
 avg(h.pickups) AS mean_pickups
FROM taxi.hourly h JOIN taxi.zones z USING(zone_id)
GROUP BY 1,2,3 ORDER BY mean_pickups DESC LIMIT 20;

-- Compare the latest day to the same weekday a week earlier.
SELECT zone,date,pickups,rolling_7d_pickups,
 100.0*(pickups-previous_week_pickups)/nullif(previous_week_pickups,0) AS wow_pct
FROM taxi.daily_trends
WHERE date=(SELECT max(date) FROM taxi.daily_trends)
ORDER BY pickups DESC LIMIT 20;

-- True held-out forecast scores, with zero-denominator protection.
SELECT z.zone,s.* FROM taxi.forecast_scores s JOIN taxi.zones z USING(zone_id)
ORDER BY model_mae DESC;

-- Reconcile materialized aggregates to accepted trip facts.
SELECT (SELECT count(*) FROM taxi.trips) AS accepted_trip_rows,
       (SELECT sum(pickups) FROM taxi.hourly) AS aggregated_pickups;
