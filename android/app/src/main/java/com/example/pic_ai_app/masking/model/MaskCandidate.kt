package com.example.pic_ai_app.masking.model

data class MaskCandidate(
    val start : Int,                //후보 시작 위치
    val endExclusive : Int,         //후보 끝난 다음 위치
    val type : MaskType,            //이름, 주소, 전화번호 등의 유형
    val source : MaskSource,        //NER, Regex, Rule 중 탐지 출처a
    val confidence: Float? = null,  //NER모델의 신뢰도
) {
    init {
        require(start >= 0){
            "start must not be negative"
        }
        require(endExclusive>start){
            "endExclusive must be greater than start"
        }
        require(confidence == null || confidence in 0f..1f){
            "confidence must be between 0 and 1"
        }
    }

}
