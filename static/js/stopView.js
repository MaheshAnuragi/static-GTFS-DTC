function defaultId() {
    if (document.getElementById('set_id').checked) {

        //if ( document.querySelector('input[name="default_id"]:checked').checked == true)
        //{
           // document.querySelector('input[name="default_id"]:checked').checked = false;
       
        document.getElementById('set_stopid').style.display = "block";

        console.log("set stop id manually");
        //document.querySelector('input[name="set_id"]:checked').checked = false;



    }

    else if (document.getElementById('default_id').checked)
    {

    document.getElementById('set_stopid').style.display = 'none';
    console.log("set default stop id");

    }

    
}

function call_tooltip1(){
    
    document.getElementById('tool_tip1').style.visibility='visible';
    document.getElementById('tool_tip1').style.display='block';
}
function validateForm2() {
    console.log("form is validated")
  var a = document.getElementById('lat_name').value;
  var b = document.getElementById('long_name').value;
  var c = document.getElementById('stop_name2').value;
  var d = document.getElementById('new_stop_id').value;
  if (!a && !b && !c && !d) {
     alert("Please Fill All Required Fields");
      return false;
    }

  var radio_button1 = document.getElementById('default_id').checked;
  var radio_button2 = document.getElementById('set_id').checked;

  if (!radio_button1){
    console.log(document.getElementById('new_stop_id').value)
    if (document.getElementById('new_stop_id').value == ''){
        alert("Please select anyone radio button");
        return false;


    }
    
  }

  //if (document.getElementById('new_stop_id').value != 'empty'){
    //document.querySelector('input[name="set_id"]:checked').checked = true;
 //}


}


// // Function to make the corresponding row editable
// function makeEditable(event) {
//   event.preventDefault();
//   var row = $(event.target).closest('tr');
//   row.find('td:not(:first-child):not(:nth-child(2))').each(function() {
//       var cellValue = $(this).text();
//       $(this).html('<input type="text" value="' + cellValue + '">');
//   });
//   row.find('.edit-link').hide();
//   row.find('.save-button').show();
// }

// // Function to save the updated row
// function saveRow(event) {
//   event.preventDefault();
//   var row = $(event.target).closest('tr');
//   row.find('td:not(:first-child):not(:nth-child(2))').each(function() {
//       var cellValue = $(this).find('input').val();
//       $(this).text(cellValue);
//   });
//   row.find('.save-button').hide();
//   row.find('.edit-link').show();
// }
