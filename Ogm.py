class Ogm:
    def __init__(self, originator, sender, ttl=7, sequence_number=0):
        self.originator = originator
        self.sender = sender
        self.ttl = ttl
        self.sequence_number = sequence_number
        
        self.id = f"{originator}_{sequence_number}"  # identificatore unico

    def clone_for_forwarding(self, new_sender):
        return Ogm(
            originator=self.originator,
            sender=new_sender,
            ttl=self.ttl - 1,
            sequence_number=self.sequence_number
        )
    
    def __str__(self):
        return f"[{self.id}] SENDER:{self.sender} TTL:{self.ttl}"