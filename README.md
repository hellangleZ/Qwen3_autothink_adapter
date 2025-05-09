# Qwen3_autothink_adapter
Implemented a script that automatically adjusts Qwen3's inference and non-inference capabilities, based on an OpenAI-like API. The inference framework can be sglang, or it can be adapted/modified to use vLLM

Idea and partial code got from https://github.com/AaronFeng753/Better-Qwen3

Thanks @AaronFeng753

This system automatically applies Qwen3's classification and 'thinking' processes using a unified model. By default, the classifier activates a 'no thinking' state to save tokens and reduce latency, with negligible impact on the overall response. The classifier then automatically selects between 'think' and 'no think' modes based on the incoming query.
The output clearly shows the debug status, whether 'thinking' mode is active, and all output content. This information can be selectively displayed.


Reaosning：
![image](https://github.com/user-attachments/assets/0bf32274-f159-4614-ae13-c3be69a937d4)
![image](https://github.com/user-attachments/assets/63bc38d3-ba55-487f-b29a-0eac33346ca1)
![image](https://github.com/user-attachments/assets/e2349a8b-4a7f-4a3d-82f0-a675fec61559)
Non-reasoning
![image](https://github.com/user-attachments/assets/e7d1dd1c-6ed0-45ed-92de-ebb0a3b02b59)
