import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import openai
import openrouteservice
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
ors_key = os.getenv("ORS_API_KEY")

# Initialize OpenRouteService client
ors_client = openrouteservice.Client(key=ors_key)

app = FastAPI(title="Safe Streets Backend", description="Backend for Safe Streets: AI-Powered Women’s Safety Navigator")


# Allowed origins (replace with the URL where your frontend is running)
origins = ["http://localhost:3000"]

# Apply CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RouteRequest(BaseModel):
    origin: str
    destination: str

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def read_root():
    return {"message": "Welcome to the Safe Streets API"}

@app.post("/get-safe-route")
async def get_safe_route(route_request: RouteRequest):
    """Generate a safe route between two locations and provide relevant alerts."""
    try:
        # Geocode origin and destination to get coordinates
        origin_search = ors_client.pelias_search(route_request.origin)
        destination_search = ors_client.pelias_search(route_request.destination)
        
        # Ensure search results contain coordinates
        if not origin_search['features'] or not destination_search['features']:
            raise HTTPException(status_code=404, detail="Could not find valid coordinates for the specified addresses.")
        
        # Extract coordinates
        origin_coords = origin_search['features'][0]['geometry']['coordinates']
        destination_coords = destination_search['features'][0]['geometry']['coordinates']
        
        print(f"Origin coordinates: {origin_coords}")
        print(f"Destination coordinates: {destination_coords}")

        # Attempt to get route suggestions from ORS for driving-car profile
        try:
            routes = ors_client.directions(
                coordinates=[origin_coords, destination_coords],
                profile="driving-car",
                format="geojson",
            )
        except openrouteservice.exceptions.ApiError as e:
            error_message = str(e)
            if "Could not find routable point within a radius" in error_message:
                print("No routable point found within the radius of destination coordinates.")
                raise HTTPException(
                    status_code=404,
                    detail="Could not find a route to the specified destination. It may be too remote for routing."
                )
            else:
                print(f"OpenRouteService API error: {error_message}")
                raise HTTPException(status_code=500, detail=f"Error generating route: {error_message}")

        # Check if route is available
        if not routes["features"]:
            raise HTTPException(status_code=404, detail="No route found between the specified locations.")

        route_coords = routes["features"][0]["geometry"]["coordinates"]
        
        print(f"Route coordinates: {route_coords}")

        # Simulate alerts based on route (this could be replaced with an actual API or database lookup)
        alerts = {
            "police_stations": 3 if origin_coords[1] > destination_coords[1] else 2,
            "public_facilities": 5 if origin_coords[0] < destination_coords[0] else 3,
            "crowd_density": "High" if origin_coords[1] < destination_coords[1] else "Medium"
        }

        return {
            "origin": {"address": route_request.origin, "coordinates": origin_coords},
            "destination": {"address": route_request.destination, "coordinates": destination_coords},
            "route": route_coords,
            "alerts": alerts
        }
    except openrouteservice.exceptions.ApiError as e:
        raise HTTPException(status_code=500, detail=f"Error generating route: {str(e)}")
    except IndexError:
        raise HTTPException(status_code=404, detail="Could not find valid coordinates for the specified addresses.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error occurred: {str(e)}")



@app.post("/ask-ai")
async def ask_ai(query_request: QueryRequest):
    """Get AI-powered safety tips or assistance."""
    try:
        if not openai.api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key is not set.")

        # Define the message for the chat model
        messages = [
            {"role": "system", "content": "You are a women's safety advisor with expertise in urban navigation, personal security, and emergency assistance."},
            {"role": "user", "content": query_request.question}
        ]

        # Use the new `openai.ChatCompletion.create` for GPT models (gpt-3.5-turbo or gpt-4)
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # or "gpt-4" if you have access
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )

        # Extract the assistant's reply
        answer = response.choices[0].message.content.strip()
        return {"response": answer}
    except Exception as e:
        # Log any other exceptions
        print(f"Unexpected error with AI response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error with AI response: {str(e)}")


@app.post("/get-safety-score")
async def get_safety_score(route: list):
    """
    Fetch safety score for the provided route coordinates from Inferell.ai.
    """
    try:
        # Example payload format for Inferell.ai (assuming it takes a list of coordinates)
        payload = {"route": route}

        # Call Inferell.ai's safety scoring endpoint (substitute with your actual endpoint and API key)
        inferell_response = requests.post(
            "https://api.inferell.ai/v1/safety_score", 
            headers={"Authorization": f"Bearer {os.getenv('INFERELL_API_KEY')}"},
            json=payload
        )

        # Check response status
        if inferell_response.status_code == 200:
            safety_data = inferell_response.json()
            return {"safety_score": safety_data.get("score", "N/A")}
        else:
            return {"safety_score": "Error fetching safety score"}
    except Exception as e:
        print(f"Error fetching safety score: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch safety score.")
        

@app.get("/alerts")
async def get_real_time_alerts():
    """Retrieve real-time safety alerts or facilities info."""
    return {
        "police_stations": 2,
        "public_facilities": 5,
        "crowd_density": "Medium"
    }
