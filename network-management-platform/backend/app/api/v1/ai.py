from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import json

from ...core.database import get_db
from ...core.auth import get_current_user
from ...models.user import User
from ....ai.main import AIOrchestrator
from ....ai.nlp.command_parser import CommandParser
from ...services.websocket_manager import manager

router = APIRouter()

# Initialize AI components
ai_orchestrator = AIOrchestrator()
command_parser = CommandParser()

class ChatRequest:
    message: str
    context: Optional[List[Dict[str, Any]]] = []
    knowledgeBase: Optional[List[Dict[str, Any]]] = []
    regenerate: Optional[bool] = False

class ChatResponse:
    response: str
    command: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[Dict[str, str]]] = None
    learnedInfo: Optional[Dict[str, Any]] = None

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process a chat message and return AI response"""
    try:
        start_time = datetime.now()
        
        # Parse command if applicable
        parsed_command = None
        if not request.regenerate:
            parsed_command = command_parser.parse(request.message)
            
            # If command is valid, execute it
            if parsed_command.get("valid"):
                agent_response = await ai_orchestrator.process_command(
                    parsed_command,
                    user_id=current_user.id
                )
                
                return ChatResponse(
                    response=agent_response.get("result", "Command executed successfully"),
                    command={
                        "intent": parsed_command["intent"],
                        "entities": parsed_command["entities"],
                        "confidence": parsed_command["confidence"],
                        "executed": True,
                        "result": agent_response
                    },
                    metadata={
                        "processingTime": (datetime.now() - start_time).total_seconds() * 1000,
                        "model": "gpt-4",
                        "sources": agent_response.get("sources", [])
                    },
                    suggestions=_generate_suggestions(parsed_command["intent"])
                )
        
        # If not a command or regenerating, use conversational AI
        conversation_response = await ai_orchestrator.chat(
            message=request.message,
            context=request.context,
            user_id=current_user.id
        )
        
        # Extract learned information for knowledge base
        learned_info = _extract_learned_info(
            request.message, 
            conversation_response,
            request.knowledgeBase
        )
        
        return ChatResponse(
            response=conversation_response["response"],
            command=parsed_command if parsed_command and not request.regenerate else None,
            metadata={
                "processingTime": (datetime.now() - start_time).total_seconds() * 1000,
                "model": conversation_response.get("model", "gpt-4"),
                "tokens": conversation_response.get("tokens", 0),
                "sources": conversation_response.get("sources", [])
            },
            suggestions=_generate_suggestions(None, request.context),
            learnedInfo=learned_info
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback")
async def submit_feedback(
    messageId: str,
    helpful: bool,
    comment: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit feedback for an AI response"""
    try:
        # Store feedback in database
        # This would typically update a feedback table
        return {"status": "success", "message": "Feedback recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time chat"""
    await manager.connect(websocket)
    
    try:
        # Authenticate user from token
        user = await get_current_user_ws(token, db)
        if not user:
            await websocket.close(code=4001, reason="Unauthorized")
            return
            
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Process message
            response = await chat(
                ChatRequest(**data),
                current_user=user,
                db=db
            )
            
            # Send response
            await websocket.send_json({
                "type": "chat_response",
                "data": response.dict()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        await websocket.close()

def _generate_suggestions(intent: Optional[str], context: Optional[List] = None) -> List[Dict[str, str]]:
    """Generate contextual suggestions based on intent and conversation context"""
    
    base_suggestions = [
        {"text": "Show system status", "category": "command", "icon": "activity"},
        {"text": "List all devices", "category": "command", "icon": "server"},
        {"text": "Run diagnostics", "category": "action", "icon": "search"},
        {"text": "Check recent alerts", "category": "command", "icon": "alert"},
    ]
    
    if intent == "network_scan":
        return [
            {"text": "Show scan results in table", "category": "command", "icon": "table"},
            {"text": "Export scan data", "category": "action", "icon": "download"},
            {"text": "Schedule regular scans", "category": "action", "icon": "clock"},
            {"text": "Compare with previous scan", "category": "command", "icon": "git-compare"},
        ]
    elif intent == "system_restart":
        return [
            {"text": "Check system logs", "category": "command", "icon": "file-text"},
            {"text": "Monitor restart progress", "category": "command", "icon": "activity"},
            {"text": "Set up restart notifications", "category": "action", "icon": "bell"},
            {"text": "Schedule maintenance window", "category": "action", "icon": "calendar"},
        ]
    elif intent == "backup_management":
        return [
            {"text": "Show backup history", "category": "command", "icon": "history"},
            {"text": "Verify backup integrity", "category": "action", "icon": "check-circle"},
            {"text": "Configure backup schedule", "category": "action", "icon": "clock"},
            {"text": "Test restore process", "category": "action", "icon": "refresh-cw"},
        ]
    
    # Context-based suggestions
    if context and len(context) > 2:
        last_messages = [msg.get("content", "") for msg in context[-3:]]
        if any("error" in msg.lower() for msg in last_messages):
            return [
                {"text": "Show error logs", "category": "command", "icon": "alert-triangle"},
                {"text": "Run system diagnostics", "category": "action", "icon": "activity"},
                {"text": "Check service status", "category": "command", "icon": "heart"},
                {"text": "Contact support", "category": "action", "icon": "headphones"},
            ]
    
    return base_suggestions

def _extract_learned_info(message: str, response: Dict, knowledge_base: List) -> Optional[Dict[str, Any]]:
    """Extract new information that should be added to the knowledge base"""
    
    # Simple heuristic: if the response contains explanations about system features
    # that aren't already in the knowledge base, suggest adding them
    
    keywords = ["you can", "this allows", "to do this", "this feature", "this helps"]
    
    if any(keyword in response.get("response", "").lower() for keyword in keywords):
        # Check if this information is already in knowledge base
        response_lower = response["response"].lower()
        for entry in knowledge_base:
            if entry.get("content", "").lower() in response_lower:
                return None
        
        # Extract a title from the response
        lines = response["response"].split(".")
        title = lines[0].strip() if lines else "New Information"
        
        # Categorize based on keywords
        category = "general"
        if any(word in message.lower() for word in ["network", "scan", "device"]):
            category = "network"
        elif any(word in message.lower() for word in ["backup", "restore", "save"]):
            category = "backup"
        elif any(word in message.lower() for word in ["monitor", "metric", "performance"]):
            category = "monitoring"
        elif any(word in message.lower() for word in ["security", "auth", "permission"]):
            category = "security"
        
        return {
            "title": title[:100],  # Limit title length
            "content": response["response"][:500],  # Limit content length
            "category": category,
            "tags": _extract_tags(message + " " + response["response"])
        }
    
    return None

def _extract_tags(text: str) -> List[str]:
    """Extract relevant tags from text"""
    
    # Common technical terms to look for
    tech_terms = [
        "network", "server", "backup", "restore", "monitor", "metric",
        "security", "authentication", "permission", "device", "system",
        "performance", "diagnostic", "alert", "notification", "schedule",
        "configuration", "database", "api", "service", "process"
    ]
    
    text_lower = text.lower()
    tags = []
    
    for term in tech_terms:
        if term in text_lower:
            tags.append(term)
    
    return tags[:5]  # Limit to 5 tags

async def get_current_user_ws(token: str, db: Session) -> Optional[User]:
    """Get current user from WebSocket token"""
    # This is a simplified version - implement proper JWT validation
    try:
        # Validate token and get user
        # ... token validation logic ...
        return None  # Placeholder
    except Exception:
        return None