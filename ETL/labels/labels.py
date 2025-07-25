import google.generativeai as genai
import json 
import time
import logging
from tqdm import tqdm
tqdm = lambda x: x

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiModel:
    """
    A class to generate unique labels for topic clusters based on their research paper titles.
    """
    
    def __init__(self, api_key, model_name="gemini-1.5-flash"):
        """
        Initialize the TopicLabeler with API key and model configuration.
        
        Parameters:
        -----------
        api_key : str
            Google Generative AI API key
        model_name : str, optional
            Name of the Gemini model to use (default is "gemini-1.5-flash")
        """
        self.api_key = api_key
        self.model_name = model_name
        self.cache = {}
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def _generate(self, prompt, delay=6):
        if prompt in self.cache:
            return self.cache[prompt]
        time.sleep(delay)  # Rate limit management
        output = self.model.generate_content(prompt).text
        self.cache[prompt] = output
        return output

    
    def _create_prompt(self, text, other_labels = None):
        """Create a prompt for processing Generating Labels"""
        prompt = f"""

        You are an AI system designed to analyze and generate labels for topic areas of research papers, 
        represented in a 2D embedding landscape. Each group of research papers share similar themes, 
        indicating a related research focus.
        YOUR MAIN TASK:
        Generate a label that distinctly characterizes this topic area of research, ensuring that the label is **unique** compared to the labels of other contour areas. 
        Steps:
        1. Review the research paper titles within this topic area to identify key recurring themes and perspectives.
        2. Compare these themes to those from other topic areas to **ensure that this label is unique** and does not overlap with others.
        Research papers in this contour area:
        {text}

        Labels from other contour areas:
        {other_labels}

        Your output must be a valid JSON object in this format:
        {{"title": "<Your descriptive label here>"}}
        
        Requirements for the label:
        - 1 - 3 words long
        - Accurately reflects what makes this research area unique
        - **Clearly distinguishes this label** from the labels of other topic areas, ensuring it is **uniquely identifiable**

        """
        
        return prompt
    
    def run(self, text, other_labels = None):
        """
        Generate unique labels for topic clusters based on their research paper titles.
        
        Parameters:
        -----------
        topic_clusters : pandas.DataFrame
            DataFrame containing topic clusters with a 'title' column of lists of paper titles
        
        Returns:
        --------
        list
            A list of generated unique labels for each topic cluster
        """
        # Initialize labels list
        labels = []
        
        # Process each topic cluster
       
        try:
            
            prompt = self._create_prompt(text, other_labels)
            # Generate label
            output = self._generate(prompt)
            
            # Parse the output
            if isinstance(output, str):
                label_result = output.strip()
                label_result = label_result.lstrip('```json').rstrip('```')
                label_result = label_result.strip()
                
                try:
                    # Try to parse as JSON
                    label_data = json.loads(label_result)
                    label = label_data['title']
                    labels.append(label)
                except Exception as e:
                    logger.error(f"Error parsing label JSON: {str(e)}")
                    labels.append(output)
        
        except Exception as e:
            logger.error(f"Error processing cluster: {str(e)}")
            labels.append(None)
    
        return labels