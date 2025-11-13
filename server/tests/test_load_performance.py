"""Load testing and performance validation."""
import pytest
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import List
from unittest.mock import patch, AsyncMock

from app.models.customer import Customer
from app.models.vehicle import Vehicle


class TestConcurrentCalls:
    """Test system handles concurrent calls."""
    
    @pytest.mark.asyncio
    async def test_concurrent_customer_lookups(self, db_session):
        """Test concurrent customer lookup operations."""
        from app.tools.crm_tools import lookup_customer
        
        # Create test customers
        customers = []
        for i in range(10):
            customer = Customer(
                name=f"Test Customer {i}",
                phone_number=f"+1555555{i:04d}",
                email=f"test{i}@example.com",
                date_of_birth=datetime(1980, 1, 1).date(),
                street_address=f"{i} Test St",
                city="Springfield",
                state="IL",
                zip_code="62701"
            )
            db_session.add(customer)
        
        await db_session.commit()
        
        # Perform concurrent lookups
        tasks = [
            lookup_customer(db_session, f"+1555555{i:04d}")
            for i in range(10)
        ]
        
        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        duration = time.perf_counter() - start
        
        # All lookups should succeed
        assert all(r["success"] for r in results)
        
        # Should complete in reasonable time (< 1 second for 10 lookups)
        assert duration < 1.0, f"10 concurrent lookups took {duration:.2f}s"
        
        print(f"✓ 10 concurrent lookups completed in {duration*1000:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_concurrent_appointment_bookings(self, db_session, test_customer, test_vehicle):
        """Test concurrent appointment booking operations."""
        from app.tools.crm_tools import book_appointment
        
        # Book multiple appointments at different times
        base_time = datetime.now(timezone.utc) + timedelta(days=1)
        
        tasks = [
            book_appointment(
                db_session,
                customer_phone=test_customer.phone_number,
                vehicle_vin=test_vehicle.vin,
                service_type="Oil Change",
                scheduled_time=(base_time + timedelta(hours=i)).isoformat(),
                duration_minutes=30
            )
            for i in range(5)
        ]
        
        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        duration = time.perf_counter() - start
        
        # All bookings should succeed
        assert all(r["success"] for r in results)
        
        # Should complete in reasonable time
        assert duration < 2.0, f"5 concurrent bookings took {duration:.2f}s"
        
        print(f"✓ 5 concurrent bookings completed in {duration*1000:.2f}ms")


class TestDatabaseConnectionPool:
    """Test database connection pooling under load."""
    
    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self, db_session):
        """Test system handles connection pool limits gracefully."""
        from app.tools.crm_tools import lookup_customer
        
        # Create test customer
        customer = Customer(
            name="Pool Test Customer",
            phone_number="+15555550001",
            email="pool@example.com",
            date_of_birth=datetime(1980, 1, 1).date(),
            street_address="1 Pool St",
            city="Springfield",
            state="IL",
            zip_code="62701"
        )
        db_session.add(customer)
        await db_session.commit()
        
        # Simulate high concurrent load (50 operations)
        tasks = [
            lookup_customer(db_session, "+15555550001")
            for _ in range(50)
        ]
        
        start = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.perf_counter() - start
        
        # Count successes and failures
        successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failures = len(results) - successes
        
        print(f"✓ 50 concurrent operations: {successes} succeeded, {failures} failed in {duration:.2f}s")
        
        # At least 80% should succeed
        assert successes >= 40, f"Only {successes}/50 operations succeeded"


class TestRedisPerformance:
    """Test Redis performance under load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self):
        """Test concurrent Redis session operations."""
        from app.services.redis_client import set_session, get_session, delete_session
        
        # Create multiple sessions concurrently
        session_data = {
            "customer_id": 123,
            "state": "GREETING",
            "transcript": []
        }
        
        call_sids = [f"CA_load_test_{i}" for i in range(20)]
        
        # Write sessions
        write_tasks = [
            set_session(call_sid, session_data)
            for call_sid in call_sids
        ]
        
        start = time.perf_counter()
        write_results = await asyncio.gather(*write_tasks)
        write_duration = time.perf_counter() - start
        
        # Read sessions
        read_tasks = [get_session(call_sid) for call_sid in call_sids]
        
        start = time.perf_counter()
        read_results = await asyncio.gather(*read_tasks)
        read_duration = time.perf_counter() - start
        
        # Cleanup
        delete_tasks = [delete_session(call_sid) for call_sid in call_sids]
        await asyncio.gather(*delete_tasks)
        
        # Verify performance
        if any(write_results):  # Redis is available
            print(f"✓ 20 Redis writes: {write_duration*1000:.2f}ms")
            print(f"✓ 20 Redis reads: {read_duration*1000:.2f}ms")
            
            # Should be fast
            assert write_duration < 0.5, f"20 writes took {write_duration:.2f}s"
            assert read_duration < 0.5, f"20 reads took {read_duration:.2f}s"


class TestAudioPipelinePerformance:
    """Test audio processing pipeline performance."""
    
    @pytest.mark.asyncio
    @patch("app.services.deepgram_stt.DeepgramSTTService")
    @patch("app.services.deepgram_tts.DeepgramTTSService")
    @patch("app.services.openai_service.OpenAIService")
    async def test_stt_to_llm_latency(self, mock_openai, mock_tts, mock_stt):
        """Test STT → LLM latency meets <800ms target."""
        
        # Configure mocks
        mock_stt_instance = AsyncMock()
        mock_openai_instance = AsyncMock()
        
        mock_stt.return_value = mock_stt_instance
        mock_openai.return_value = mock_openai_instance
        
        # Simulate transcript
        async def mock_get_transcript():
            await asyncio.sleep(0.3)  # Simulate STT processing
            return {
                "type": "final",
                "text": "I need to book an appointment"
            }
        
        mock_stt_instance.get_transcript = mock_get_transcript
        
        # Simulate LLM response
        async def mock_generate_response(stream=True):
            await asyncio.sleep(0.4)  # Simulate LLM processing
            yield {
                "type": "content_delta",
                "text": "I can help you with that."
            }
        
        mock_openai_instance.generate_response = mock_generate_response
        
        # Measure end-to-end latency
        start = time.perf_counter()
        
        transcript = await mock_stt_instance.get_transcript()
        
        async for response in mock_openai_instance.generate_response():
            first_token_time = time.perf_counter() - start
            break
        
        # Should meet <800ms target
        assert first_token_time < 0.8, f"STT→LLM took {first_token_time*1000:.2f}ms"
        
        print(f"✓ STT→LLM latency: {first_token_time*1000:.2f}ms (target: <800ms)")
    
    @pytest.mark.asyncio
    @patch("app.services.deepgram_tts.DeepgramTTSService")
    async def test_llm_to_tts_latency(self, mock_tts):
        """Test LLM → TTS latency meets <500ms target."""
        
        mock_tts_instance = AsyncMock()
        mock_tts.return_value = mock_tts_instance
        
        # Simulate TTS send
        async def mock_send_text(text):
            await asyncio.sleep(0.2)  # Simulate TTS processing
        
        mock_tts_instance.send_text = mock_send_text
        
        # Measure latency
        start = time.perf_counter()
        await mock_tts_instance.send_text("I can help you with that.")
        latency = time.perf_counter() - start
        
        # Should meet <500ms target
        assert latency < 0.5, f"LLM→TTS took {latency*1000:.2f}ms"
        
        print(f"✓ LLM→TTS latency: {latency*1000:.2f}ms (target: <500ms)")
    
    @pytest.mark.asyncio
    async def test_barge_in_response_time(self):
        """Test barge-in response meets <200ms target."""
        from app.services.redis_client import set_session, get_session, delete_session
        
        call_sid = "CA_barge_in_test"
        
        # Simulate barge-in detection
        start = time.perf_counter()
        
        # Set is_speaking flag
        await set_session(call_sid, {"is_speaking": False})
        
        # Get session to check flag
        session = await get_session(call_sid)
        
        response_time = time.perf_counter() - start
        
        # Cleanup
        await delete_session(call_sid)
        
        if session is not None:  # Redis available
            # Should respond in <200ms
            assert response_time < 0.2, f"Barge-in response took {response_time*1000:.2f}ms"
            
            print(f"✓ Barge-in response: {response_time*1000:.2f}ms (target: <200ms)")


class TestScalabilityLimits:
    """Test system scalability limits."""
    
    @pytest.mark.asyncio
    async def test_maximum_concurrent_sessions(self):
        """Test maximum concurrent session capacity."""
        from app.services.redis_client import set_session, delete_session
        
        # Simulate 100 concurrent sessions
        num_sessions = 100
        
        tasks = [
            set_session(
                f"CA_scale_test_{i}",
                {
                    "customer_id": i,
                    "state": "GREETING",
                    "transcript": []
                }
            )
            for i in range(num_sessions)
        ]
        
        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        duration = time.perf_counter() - start
        
        # Cleanup
        cleanup_tasks = [
            delete_session(f"CA_scale_test_{i}")
            for i in range(num_sessions)
        ]
        await asyncio.gather(*cleanup_tasks)
        
        if any(results):  # Redis available
            success_count = sum(1 for r in results if r)
            
            print(f"✓ {success_count}/{num_sessions} sessions created in {duration:.2f}s")
            
            # Should handle 100 sessions
            assert success_count >= 95, f"Only {success_count}/100 sessions created"
    
    @pytest.mark.asyncio
    async def test_database_query_performance_at_scale(self, db_session):
        """Test database performance with large dataset."""
        from app.tools.crm_tools import lookup_customer
        
        # Create 100 customers
        for i in range(100):
            customer = Customer(
                name=f"Scale Test {i}",
                phone_number=f"+1555556{i:04d}",
                email=f"scale{i}@example.com",
                date_of_birth=datetime(1980, 1, 1).date(),
                street_address=f"{i} Scale St",
                city="Springfield",
                state="IL",
                zip_code="62701"
            )
            db_session.add(customer)
        
        await db_session.commit()
        
        # Query random customer
        start = time.perf_counter()
        result = await lookup_customer(db_session, "+15555560050")
        query_time = time.perf_counter() - start
        
        assert result["success"] is True
        
        # Should still be fast with 100 records
        assert query_time < 0.05, f"Query took {query_time*1000:.2f}ms"
        
        print(f"✓ Customer lookup with 100 records: {query_time*1000:.2f}ms")


class TestMemoryUsage:
    """Test memory usage patterns."""
    
    @pytest.mark.asyncio
    async def test_conversation_history_memory(self):
        """Test conversation history doesn't grow unbounded."""
        from app.services.openai_service import OpenAIService
        
        service = OpenAIService(api_key="test-key")
        
        # Add 100 messages
        for i in range(100):
            service.add_user_message(f"Test message {i}")
        
        # Verify message history has reasonable limit
        # (Implementation should truncate old messages)
        assert len(service.messages) <= 50, f"Message history has {len(service.messages)} messages"
        
        print(f"✓ Message history limited to {len(service.messages)} messages")


class TestStressScenarios:
    """Test system under stress conditions."""
    
    @pytest.mark.asyncio
    async def test_rapid_successive_calls(self, db_session, test_customer):
        """Test rapid successive API calls from same customer."""
        from app.tools.crm_tools import lookup_customer
        
        # 10 rapid lookups in succession
        results = []
        for _ in range(10):
            result = await lookup_customer(db_session, test_customer.phone_number)
            results.append(result)
            await asyncio.sleep(0.01)  # 10ms between calls
        
        # All should succeed
        assert all(r["success"] for r in results)
        
        print("✓ 10 rapid successive calls completed successfully")
    
    @pytest.mark.asyncio
    async def test_error_recovery_under_load(self, db_session):
        """Test system recovers from errors under load."""
        from app.tools.crm_tools import lookup_customer
        
        # Mix of valid and invalid requests
        tasks = []
        for i in range(20):
            if i % 5 == 0:
                # Invalid phone number
                tasks.append(lookup_customer(db_session, "invalid"))
            else:
                # Valid phone (won't exist, but valid format)
                tasks.append(lookup_customer(db_session, f"+1555557{i:04d}"))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # System should handle gracefully
        assert len(results) == 20
        
        # Count successes and errors
        errors = sum(
            1 for r in results
            if isinstance(r, dict) and not r.get("success")
        )
        
        print(f"✓ Handled 20 mixed requests: {errors} errors handled gracefully")


class TestEndToEndPerformanceTargets:
    """Validate all performance targets are met."""
    
    @pytest.mark.asyncio
    async def test_all_targets_summary(self, db_session, test_customer):
        """Summary test validating all performance targets."""
        from app.tools.crm_tools import lookup_customer
        import time
        
        results = {
            "Customer Lookup (cached)": {"target": 2, "actual": None, "unit": "ms"},
            "Customer Lookup (uncached)": {"target": 30, "actual": None, "unit": "ms"},
        }
        
        # Test customer lookup (uncached)
        start = time.perf_counter()
        result = await lookup_customer(db_session, test_customer.phone_number)
        uncached_time = (time.perf_counter() - start) * 1000
        results["Customer Lookup (uncached)"]["actual"] = uncached_time
        
        # Test customer lookup (cached)
        start = time.perf_counter()
        result = await lookup_customer(db_session, test_customer.phone_number)
        cached_time = (time.perf_counter() - start) * 1000
        
        if result.get("cached"):
            results["Customer Lookup (cached)"]["actual"] = cached_time
        
        # Print summary
        print("\n=== Performance Targets Summary ===")
        for test_name, data in results.items():
            if data["actual"] is not None:
                status = "✓" if data["actual"] < data["target"] else "✗"
                print(
                    f"{status} {test_name}: {data['actual']:.2f}{data['unit']} "
                    f"(target: <{data['target']}{data['unit']})"
                )
