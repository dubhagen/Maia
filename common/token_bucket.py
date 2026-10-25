import threading
import time


class TokenBucket:
    def __init__(self, tpm, timeout=None):
        self.capacity = int(tpm)  
        self.tokens = 0  
        self.rate = int(tpm) / 60  
        self.timeout = timeout  
        self.cond = threading.Condition()  
        self.is_running = True
        # Start the token generator thread. It must be a daemon: a rate limiter
        # has no reason to keep the process from exiting, and both production
        # call sites build a bucket without ever calling close().
        self._thread = threading.Thread(target=self._generate_tokens, daemon=True)
        self._thread.start()

    def _generate_tokens(self):
        """Add tokens up to the bucket capacity."""
        if self.rate <= 0:
            # A sub-1 tokens-per-minute config rounds to a rate of zero, so
            # there is nothing to generate. Stop here instead of dividing by 0
            # in the sleep below, which would kill this thread silently.
            with self.cond:
                self.is_running = False
                self.cond.notify_all()
            return
        while self.is_running:
            with self.cond:
                if self.tokens < self.capacity:
                    self.tokens += 1
                self.cond.notify()  
            time.sleep(1 / self.rate)

    def get_token(self):
        """Take one token, waiting until the timeout."""
        with self.cond:
            deadline = time.monotonic() + self.timeout if self.timeout is not None else None
            while self.tokens <= 0:
                if not self.is_running:
                    return False
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return False
                flag = self.cond.wait(remaining)
                if not flag:  
                    return False
            if not self.is_running:
                return False
            self.tokens -= 1
        return True

    def close(self):
        with self.cond:
            self.is_running = False
            self.cond.notify_all()
        # The generator may be mid-sleep, so bound the wait. It is a daemon
        # thread, so a missed join can never keep the process alive.
        self._thread.join(timeout=1)


if __name__ == "__main__":
    token_bucket = TokenBucket(20, None)  
    # token_bucket = TokenBucket(20, 0.1)
    for i in range(3):
        if token_bucket.get_token():
            print(f"request {i + 1} ok")
    token_bucket.close()
