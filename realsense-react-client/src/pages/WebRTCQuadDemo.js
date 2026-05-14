import React, { useState, useEffect, useRef, useCallback } from 'react';
import cloudSignalingService from '../services/cloudSignalingService';

const STREAM_TYPES = ['color', 'depth', 'infrared-1', 'infrared-2'];
const STREAM_LABELS = ['Color', 'Depth', 'Infrared 1', 'Infrared 2'];

/**
 * Cloud WebRTC demo: pick a robot, then one session streams four modalities at once.
 */
const WebRTCQuadDemo = () => {
  const [availableRobots, setAvailableRobots] = useState([]);
  const [selectedRobotId, setSelectedRobotId] = useState('');
  const [signalingConnected, setSignalingConnected] = useState(false);
  const [status, setStatus] = useState('Connecting to cloud…');
  const [statusType, setStatusType] = useState('info');

  const pcRef = useRef(null);
  const sessionIdRef = useRef(null);
  const trackIndexRef = useRef(0);
  const videoRefs = useRef([null, null, null, null]);
  const mountedRef = useRef(true);

  const updateStatus = useCallback((message, type = 'info') => {
    setStatus(message);
    setStatusType(type);
  }, []);

  const teardown = useCallback(async () => {
    const sid = sessionIdRef.current;
    sessionIdRef.current = null;
    if (sid) {
      try {
        await cloudSignalingService.closeSession(sid);
      } catch {
        /* ignore */
      }
    }
    if (pcRef.current) {
      try {
        pcRef.current.close();
      } catch {
        /* ignore */
      }
      pcRef.current = null;
    }
    trackIndexRef.current = 0;
    for (let i = 0; i < videoRefs.current.length; i++) {
      const el = videoRefs.current[i];
      if (el) el.srcObject = null;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    const setup = async () => {
      try {
        await cloudSignalingService.connect();
        if (cancelled) return;
        setSignalingConnected(true);
        updateStatus('Cloud connected — select a robot', 'success');
      } catch (e) {
        if (!cancelled) {
          setSignalingConnected(false);
          updateStatus(`Cloud connection failed: ${e.message}`, 'error');
        }
      }
    };

    const onRobots = (robots) => setAvailableRobots(robots);
    const onAvail = (robot) => {
      setAvailableRobots((prev) => [...prev.filter((r) => r.robotId !== robot.robotId), robot]);
    };
    const onGone = (robot) => {
      setAvailableRobots((prev) => prev.filter((r) => r.robotId !== robot.robotId));
      setSelectedRobotId((id) => (id === robot.robotId ? '' : id));
    };
    const onDisc = () => setSignalingConnected(false);
    const onRe = () => setSignalingConnected(true);

    cloudSignalingService.addEventListener('available-robots', onRobots);
    cloudSignalingService.addEventListener('robot-available', onAvail);
    cloudSignalingService.addEventListener('robot-unavailable', onGone);
    cloudSignalingService.addEventListener('disconnected', onDisc);
    cloudSignalingService.addEventListener('reconnected', onRe);

    setup();

    return () => {
      cancelled = true;
      mountedRef.current = false;
      teardown();
      cloudSignalingService.removeEventListener('available-robots', onRobots);
      cloudSignalingService.removeEventListener('robot-available', onAvail);
      cloudSignalingService.removeEventListener('robot-unavailable', onGone);
      cloudSignalingService.removeEventListener('disconnected', onDisc);
      cloudSignalingService.removeEventListener('reconnected', onRe);
      cloudSignalingService.disconnect();
    };
  }, [teardown, updateStatus]);

  useEffect(() => {
    if (!signalingConnected || !selectedRobotId) {
      teardown();
      if (signalingConnected && !selectedRobotId) {
        updateStatus('Cloud connected — select a robot', 'info');
      }
      return undefined;
    }

    const robot = cloudSignalingService.getAvailableRobots().find((r) => r.robotId === selectedRobotId);
    if (!robot) {
      updateStatus('Selected robot is no longer available', 'error');
      return undefined;
    }

    let alive = true;

    (async () => {
      try {
        await teardown();
        if (!alive || !mountedRef.current) return;

        updateStatus('Starting four-stream WebRTC session…', 'info');
        trackIndexRef.current = 0;

        const sessionData = await cloudSignalingService.createSession(
          robot.robotId,
          robot.deviceInfo.deviceId,
          STREAM_TYPES
        );
        if (!alive || !mountedRef.current) return;

        const { sessionId, offer } = sessionData;
        sessionIdRef.current = sessionId;

        if (!offer?.sdp || !offer?.type) {
          throw new Error('Invalid WebRTC offer from robot');
        }

        const pc = new RTCPeerConnection({
          iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
        });
        pcRef.current = pc;

        pc.ontrack = (event) => {
          const idx = Math.min(trackIndexRef.current++, STREAM_TYPES.length - 1);
          const video = videoRefs.current[idx];
          if (video) {
            video.srcObject = new MediaStream([event.track]);
          }
        };

        pc.onicecandidate = async (event) => {
          if (event.candidate && sessionIdRef.current) {
            try {
              await cloudSignalingService.sendIceCandidate(sessionIdRef.current, event.candidate);
            } catch {
              /* ignore */
            }
          }
        };

        await pc.setRemoteDescription(new RTCSessionDescription(offer));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        await cloudSignalingService.sendAnswer(sessionId, answer);

        if (!alive || !mountedRef.current) return;

        updateStatus(`Streaming: ${STREAM_TYPES.join(', ')}`, 'success');
      } catch (e) {
        if (alive && mountedRef.current) {
          updateStatus(e.message || String(e), 'error');
        }
      }
    })();

    return () => {
      alive = false;
      teardown();
    };
  }, [selectedRobotId, signalingConnected, teardown, updateStatus]);

  useEffect(() => {
    if (availableRobots.length === 0 || selectedRobotId) return;
    setSelectedRobotId(availableRobots[0].robotId);
  }, [availableRobots, selectedRobotId]);

  return (
    <div>
      <div className="container">
        <h2>🎛️ Multi-stream WebRTC (cloud)</h2>
        <p>
          Choose a registered robot. The page opens one WebRTC session with{' '}
          <strong>color, depth, infrared-1, and infrared-2</strong> together.
        </p>

        <div className="form-group">
          <label htmlFor="quadRobotSelect">Robot</label>
          <select
            id="quadRobotSelect"
            value={selectedRobotId}
            onChange={(e) => setSelectedRobotId(e.target.value)}
            disabled={!signalingConnected || availableRobots.length === 0}
          >
            {availableRobots.length === 0 ? (
              <option value="">No robots online</option>
            ) : (
              availableRobots.map((r) => (
                <option key={r.robotId} value={r.robotId}>
                  {r.deviceInfo?.name || r.robotId} — {r.deviceInfo?.deviceId || 'device'}
                </option>
              ))
            )}
          </select>
        </div>

        <div className={`status ${signalingConnected ? 'success' : 'error'}`}>
          Cloud: {signalingConnected ? 'connected' : 'disconnected'} · Robots: {availableRobots.length}
        </div>
        <div className={`status ${statusType}`}>{status}</div>
      </div>

      <div className="container">
        <h2>📺 Streams</h2>
        <div className="multi-stream-grid">
          {STREAM_LABELS.map((label, i) => (
            <div key={label} className="multi-stream-panel">
              <h3>{label}</h3>
              <video
                ref={(el) => {
                  videoRefs.current[i] = el;
                }}
                autoPlay
                playsInline
                muted
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WebRTCQuadDemo;
