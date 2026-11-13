# Data source and ticker maintenance

`nse_universe.json` is a curated suggestion list inherited from the original project, not a complete or official NSE constituent list. Verify symbols against NSE before using them for live analysis.

Selected symbol corrections confirmed against NSE disclosures / quote pages as of 13 November 2026:

- Zomato Limited changed its name and symbol to ETERNAL Limited / `ETERNAL`, effective 9 April 2025: https://nsearchives.nseindia.com/content/circulars/CML67420.pdf
- Tata Motors Passenger Vehicles changed from `TATAMOTORS` to `TMPV`, effective 24 October 2025: https://nsearchives.nseindia.com/content/circulars/CML70875.pdf
- Tata Motors Commercial Vehicles is listed under `TMCV`; NSE's quote page showed the security as listed and active on 12 November 2026: https://www.nseindia.com/get-quote/equity/TMCV/Tata-Motors

Yahoo Finance uses the `.NS` suffix for these NSE equity symbols. The app appends it for historical data requests; the visible inputs and stored watchlist symbols remain the exchange symbols without the suffix.
