from fastapi import APIRouter, Depends, HTTPException, Path
from typing import List, Dict, Any


from app.models.webrtc import WebRTCOffer, WebRTCAnswer, WebRTCStatus, ICECandidate
from app.services.webrtc_manager import WebRTCManager
from app.api.dependencies import get_webrtc_manager

router = APIRouter()

@router.post("/offer", response_model=Dict[str, Any])
async def create_offer(
    offer_request: WebRTCOffer,
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
    # user: dict = Depends(get_current_user) # -> enable this if security is needed
):
    """
    Create a WebRTC offer for streaming from a RealSense device.
    
    This endpoint supports multiple concurrent browser connections.
    Each browser will get its own session ID and can stream independently.
    The device stream is automatically managed using reference counting.
    """
    try:
        session_id, offer = await webrtc_manager.create_offer(
            offer_request.device_id,
            offer_request.stream_types
        )
        return {
            "session_id": session_id,
            "sdp": offer["sdp"],
            "type": offer["type"]
        }
    except Exception as e:
        # Log the error for debugging
        print(f"Error creating WebRTC offer: {str(e)}")
        
        # Return a more informative error message
        if "Failed to start device stream" in str(e):
            raise HTTPException(status_code=400, detail=f"Failed to start device stream: {str(e)}")
        elif "Stream type" in str(e) and "not active" in str(e):
            raise HTTPException(status_code=400, detail=f"Stream type not available: {str(e)}")
        elif "Device" in str(e) and "not streaming" in str(e):
            raise HTTPException(status_code=400, detail=f"Device not streaming: {str(e)}")
        elif "Maximum concurrent sessions" in str(e):
            raise HTTPException(status_code=429, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=f"Failed to create WebRTC offer: {str(e)}")

@router.post("/answer", response_model=dict)
async def process_answer(
    answer: WebRTCAnswer,
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Process a WebRTC answer from a client.
    """
    try:
        result = await webrtc_manager.process_answer(
            answer.session_id,
            answer.sdp,
            answer.type
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ice-candidates", response_model=dict)
async def add_ice_candidate(
    candidate: ICECandidate,
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Add an ICE candidate to a WebRTC session.
    """
    try:
        result = await webrtc_manager.add_ice_candidate(
            candidate.session_id,
            candidate.candidate,
            candidate.sdpMid,
            candidate.sdpMLineIndex
        )
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/sessions", response_model=List[WebRTCStatus])
async def list_all_sessions(
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Get the status of all active WebRTC sessions.
    
    This endpoint shows all currently active browser connections
    and their streaming status.
    """
    try:
        return await webrtc_manager.get_all_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}", response_model=WebRTCStatus)
async def get_session_status(
    session_id: str,
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Get the status of a specific WebRTC session.
    """
    try:
        return await webrtc_manager.get_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/sessions/{session_id}/ice-candidates", response_model=List[Dict[str, Any]])
async def get_ice_candidates(
    session_id: str = Path(..., description="WebRTC session ID"),
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Get ICE candidates for a WebRTC session.

    This endpoint returns all ICE candidates that have been generated
    for the specified WebRTC session.
    """
    try:
        candidates = await webrtc_manager.get_ice_candidates(session_id)
        return candidates
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/sessions/{session_id}", response_model=Dict[str, bool])
async def close_session(
    session_id: str = Path(..., description="WebRTC session ID"),
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Close a specific WebRTC session.

    This endpoint terminates the WebRTC connection and removes the session.
    All associated resources will be freed. The device stream will only be
    stopped if no other sessions are using it.
    """
    try:
        result = await webrtc_manager.close_session(session_id)
        return {"success": result}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/sessions", response_model=Dict[str, int])
async def close_all_sessions(
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Close all active WebRTC sessions.

    This endpoint terminates all WebRTC connections and removes all sessions.
    Useful for cleanup or when restarting the streaming service.
    """
    try:
        closed_count = await webrtc_manager.close_all_sessions()
        return {"closed_sessions": closed_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream-references", response_model=Dict[str, Any])
async def get_stream_references(
    webrtc_manager: WebRTCManager = Depends(get_webrtc_manager),
):
    """
    Get information about stream references for debugging.
    
    This endpoint shows the reference counting system that manages
    independent browser connections. Useful for debugging session
    management and understanding which browsers are using which streams.
    """
    try:
        return await webrtc_manager.get_stream_reference_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))