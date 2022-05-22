import pandas as pd
import os
import multiprocessing
import sys
from time import time
from time import sleep
import random

from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoConfig
import torch
from torch.utils.data import TensorDataset, DataLoader
import torch.optim as optim

# folder of sentence-level data
folder_source = "./testimony-filtered/"#"./speech-filtered/"

# folder of sentence-level data
folder_out = "./testimony-filtered-labeled/"#"./speech-filtered-labeled/"

def hawkish_dovish_classifier(list_of_sentences):
    """
    Description: Function returns label on hawkish, dovish and neutral classification for sentences based on model saved
    """
    tokenizer = AutoTokenizer.from_pretrained("../model_data/final_model", do_lower_case=True, do_basic_tokenize=True)

    model = AutoModelForSequenceClassification.from_pretrained("../model_data/final_model", num_labels=3)

    config = AutoConfig.from_pretrained("../model_data/final_model")

    machine = "gpu"
    if machine=="gpu":
        classifier = pipeline('text-classification', model=model, tokenizer=tokenizer, config=config, device=1, framework="pt")
        results = classifier(list_of_sentences, batch_size=128, truncation="only_first", device=1)
    else:
        classifier = pipeline('text-classification', model=model, tokenizer=tokenizer, config=config, device=-1, framework="pt")
        results = classifier(list_of_sentences, truncation="only_first", device=-1)
    

    return results


# read one sentence-level file
def classifier_func(index, index_df):

    if not index % 10:
        print(index)

    filename = index_df.loc[index,'filename']

    output_filename = folder_out + "labeled_" + filename
    if (not os.path.exists(output_filename)):

        # read sentence-level data
        meeting_minutes = pd.read_csv(folder_source + filename)
        
        # extract the sentences
        sentence_list = list(meeting_minutes['sentence'])

        if len(sentence_list) > 0:
        
            # feed into classifier
            result = hawkish_dovish_classifier(sentence_list)
            
            # get data frame 
            result_df = pd.DataFrame.from_dict(result)
            
            # store into the sub-dataframe
            meeting_minutes['label'] = result_df['label']
            meeting_minutes['score'] = result_df['score']
        
        # export data 
        meeting_minutes.to_csv(output_filename, index=False)
    
    return


def main_func(start_loc, end_loc, url_df, return_dict):
    # set error dataframe
    error_df = pd.DataFrame()

    index_df = url_df.iloc[start_loc:end_loc,:]
    #index_df.reset_index(inplace=True, drop = True)

    for index, row in index_df.iterrows():
        try:
            classifier_func(index, index_df)
        except Exception as e:
            # store error information if not run successfully
            print(e)
            if str(e) != "list index out of range":
                #torch.cuda.empty_cache()
                sleep_time = random.randint(10, 50)
                sleep(sleep_time)
                error_df = error_df.append(pd.DataFrame({'filename':[str(index_df.loc[index,'filename'])] }),ignore_index=True)
                return_dict['curr_loc'] = index + 1
                return (index + 1)
    # export error dataframe
    folder_error = "./error_log/"
    error_df.to_csv(folder_error + 'error' + '_'  + str(start_loc) + '_' + str(end_loc) +'.csv', index=False)


def error_handling_fn(start_loc, end_loc, url_df):
    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    current_start_loc = start_loc

    error_flag = False
    while current_start_loc < (end_loc-5):
        p = multiprocessing.Process(target = main_func, kwargs={'start_loc':int(current_start_loc), 'end_loc':int(end_loc), 'url_df':url_df, 'return_dict': return_dict})
        p.start()
        p.join()
        print(return_dict.values())
        current_start_loc_list = return_dict.values()
        current_start_loc = current_start_loc_list[0]
        print(current_start_loc)
    return 0


def execute_1(n=4):
    number_threads = int(n)

    filenames = [x for x in os.listdir(folder_source)]
    url_df = pd.DataFrame({'filename':filenames})
    

    start, end = 0, len(url_df.index)
    #end = 100
    print('number of files', end)
    if end % number_threads:
        end = (int(end/number_threads) + 1) * number_threads
    threads = [ multiprocessing.Process(target = error_handling_fn, kwargs={'start_loc':int(i), 'end_loc':int(j), 'url_df':url_df}) for (i,j) in [((end-start)/number_threads*k, (end-start)/number_threads*(k+1)) for k in range(number_threads)] ]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    

if __name__=='__main__':
    os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
    start = time()
    n_threads = sys.argv[1]
    execute_1(n=n_threads)
    print((time() - start)/60.0)
