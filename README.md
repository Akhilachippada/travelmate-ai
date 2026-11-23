# TravelMate AI – Multi-Agent Travel Planner
FastAPI + LangGraph backend, vanilla-JS frontend (colourful UI, Leaflet map).

🌐 Live demo: https://travelmate-ai-0tn1.onrender.com

## Run
```
pip install -r requirements.txt
cd backend && uvicorn main:app --reload
# open http://localhost:8000
```
Optional: `ANTHROPIC_API_KEY` (LLM chat), `JWT_SECRET`.

## Architecture
Supervisor → (Destination ∥ Transport ∥ Accommodation ∥ Weather) → Itinerary → Budget (3 scenarios) → Validator.
Weather uses Open-Meteo (no key); rainy days swap outdoor activities for indoor ones. Transport/stay prices are labelled *estimates* (no invented availability).
Images are hot-linked from Wikimedia Commons (gradient fallback if one fails) – edit `DEST[...]["img"]` in `backend/agents.py`.
Not included: multi-city trips, group-preference voting, live provider APIs.
