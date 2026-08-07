import random

def randomize_and_execute():
    # Randomly choose between picking just 1, or picking both 2 and 3 together
    choice_group = random.choice([1, (2, 3)])
    
    if choice_group == 1:
        print("Selected: 1")
        # Perform action for 1
        result = [1]
    else:
        print("Selected: 2 and 3")
        # Perform action for 2 and 3
        result = [2, 3]
        
    return result

if __name__ == "__main__":
    randomize_and_execute()
