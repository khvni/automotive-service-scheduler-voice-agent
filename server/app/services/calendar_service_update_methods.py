# This is a reference file showing the updated methods with retry logic and metrics
# These will be manually integrated into calendar_service.py

async def update_calendar_event_with_retry(
    self,
    event_id: str,
    title: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Update with retry logic and metrics tracking."""
    metrics_tracker = get_metrics_tracker()
    metric = metrics_tracker.start_operation("update_event")
    
    try:
        async def _update_event():
            service = self.get_calendar_service()
            logger.info(f"Updating calendar event: {event_id}")
            
            # Get existing event
            event = await asyncio.get_event_loop().run_in_executor(
                None, lambda: service.events().get(calendarId="primary", eventId=event_id).execute()
            )
            
            # Update fields as before...
            # (same logic as original)
            
            updated_event = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.events()
                .update(calendarId="primary", eventId=event_id, body=event, sendUpdates="all")
                .execute(),
            )
            
            return {
                "success": True,
                "event_id": updated_event.get("id"),
                "calendar_link": updated_event.get("htmlLink"),
                "message": "Event updated successfully",
            }
        
        result = await with_retry(
            _update_event,
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
            operation_name="Calendar Event Update",
        )
        
        metric.mark_success()
        metrics_tracker.record_operation(metric)
        return result
        
    except Exception as e:
        metric.mark_failure(e)
        metrics_tracker.record_operation(metric)
        logger.error(f"Error updating calendar event after retries: {e}", exc_info=True)
        return {
            "success": False,
            "event_id": event_id,
            "calendar_link": None,
            "message": f"Failed to update event: {str(e)}",
        }


async def cancel_calendar_event_with_retry(self, event_id: str) -> Dict[str, bool]:
    """Cancel with retry logic and metrics tracking."""
    metrics_tracker = get_metrics_tracker()
    metric = metrics_tracker.start_operation("delete_event")
    
    try:
        async def _cancel_event():
            service = self.get_calendar_service()
            logger.info(f"Cancelling calendar event: {event_id}")
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.events()
                .delete(calendarId="primary", eventId=event_id, sendUpdates="all")
                .execute(),
            )
            
            return {"success": True, "message": "Event cancelled successfully"}
        
        result = await with_retry(
            _cancel_event,
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
            operation_name="Calendar Event Cancellation",
        )
        
        metric.mark_success()
        metrics_tracker.record_operation(metric)
        return result
        
    except Exception as e:
        metric.mark_failure(e)
        metrics_tracker.record_operation(metric)
        logger.error(f"Error cancelling calendar event after retries: {e}", exc_info=True)
        return {"success": False, "message": f"Failed to cancel event: {str(e)}"}
